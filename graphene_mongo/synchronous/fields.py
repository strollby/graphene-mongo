import logging
from functools import partial
from itertools import filterfalse

import graphene
import mongoengine
import pymongo
from bson import DBRef
from graphene import Context
from graphene.relay import ConnectionField
from graphql import GraphQLResolveInfo
from graphql_relay import cursor_to_offset, from_global_id
from mongoengine import QuerySet
from promise import Promise
from pymongo.errors import OperationFailure

from ..base.fields import BaseMongoengineConnectionField
from ..base.utils import (
    ExecutorEnum,
    connection_from_iterables,
    find_skip_and_limit,
    has_page_info,
)

PYMONGO_VERSION = tuple(pymongo.version_tuple[:2])


class MongoengineConnectionField(BaseMongoengineConnectionField):
    """Relay ConnectionField for synchronous MongoEngine queries.

    Extends BaseMongoengineConnectionField with
    sync-specific implementations of get_queryset, default_resolver,
    chained_resolver, and connection_resolver.

    Accepted in Meta.connection_field_class of
    MongoengineObjectType subclasses.
    """

    @property
    def executor(self) -> ExecutorEnum:
        """Return ExecutorEnum.SYNC to indicate synchronous execution.

        Returns:
            ExecutorEnum: Always ExecutorEnum.SYNC.
        """
        return ExecutorEnum.SYNC

    @property
    def type(self):
        """Return the Relay connection type for this field.

        Validates that the underlying graphene type is a
        MongoengineObjectType and that
        it has an associated connection class.

        Returns:
            type: The connection class (e.g., ArticleTypeConnection).

        Raises:
            AssertionError: If the type is not a MongoengineObjectType or has no connection.
        """
        from .types import MongoengineObjectType

        _type = super(ConnectionField, self).type
        assert issubclass(_type, MongoengineObjectType), (
            "MongoengineConnectionField only accepts MongoengineObjectType types"
        )
        assert _type._meta.connection, "The type {} doesn't have a connection".format(
            _type.__name__
        )
        return _type._meta.connection

    def get_queryset(
        self, model, info, required_fields=None, skip=None, limit=None, **args
    ) -> QuerySet:
        """Build and return a synchronous MongoEngine QuerySet.

        Hydrates reference and geo arguments, delegates to a user-supplied
        get_queryset callback if provided, applies select_related, projects to
        required_fields, and applies skip / limit pagination.

        Args:
            model: MongoEngine Document class to query.
            info: GraphQL resolve info object.
            required_fields (list[str] | None): Fields to project with .only().
            skip (int | None): Number of documents to skip; None means no skip.
            limit (int | None): Maximum documents to return; None means no limit.
            **args: Additional MongoEngine filter keyword arguments.

        Returns:
            QuerySet: The constructed (and optionally paginated) QuerySet.
        """
        if required_fields is None:
            required_fields = list()
        if args:
            self._hydrate_args(args)
        if self._get_queryset:
            queryset_or_filters = self._get_queryset(model, info, **args)
            if isinstance(queryset_or_filters, mongoengine.QuerySet):
                return queryset_or_filters
            args.update(queryset_or_filters)
        qs = self._apply_select_related(
            self._qs_accessor(model)(**args).only(*required_fields).order_by(self.order_by),
            model,
            info,
        )
        if limit is not None:
            return qs.skip(skip if skip else 0).limit(limit)
        elif skip is not None:
            return qs.skip(skip)
        return qs

    def default_resolver(self, _root, info, required_fields=None, resolved=None, **args):
        """Resolve a connection field synchronously, returning a Relay-compatible connection.

        Handles three resolution scenarios:

        1. **Pre-resolved iterable** (resolved is set): Applies pagination directly
           to the provided QuerySet or list.
        2. **pk__in shortcut**: When a parent document's relation IDs were captured
           in args[ "pk__in"], fetches only those documents.
        3. **Normal query**: Issues a counted or uncounted query against the model,
           optionally using the user-supplied get_queryset callback, and applies
           Relay cursor pagination.

        Page-info computation is gated on has_page_info(info) to avoid unnecessary
        count_documents calls when the client doesn't request pageInfo.

        Args:
            _root: The parent document instance, or None for top-level queries.
            info: GraphQL resolve info object.
            required_fields (list[str] | None): Fields to project with .only().
            resolved: Pre-resolved iterable (QuerySet or list), or None.
            **args: MongoEngine filter and Relay pagination arguments
                (first, last, before, after, etc.).

        Returns:
            Connection: A graphene Relay connection with edges, pageInfo,
            iterable, and list_length populated.
        """
        if required_fields is None:
            required_fields = list()
        args = args or {}
        for key, value in dict(args).items():
            if value is None:
                del args[key]

        field_name, resolved = self._prepare_resolver_inputs(_root, info, args, resolved)

        _id = args.pop("id", None)
        if _id is not None:
            args["pk"] = from_global_id(_id)[-1]

        iterables = []
        list_length = 0
        skip = 0
        count = 0
        limit = None
        first = args.pop("first", None)
        after = args.pop("after", None)
        if after:
            after = cursor_to_offset(after)
        last = args.pop("last", None)
        before = args.pop("before", None)
        if before:
            before = cursor_to_offset(before)
        requires_page_info = has_page_info(info)
        has_next_page = False

        if resolved is not None:
            items = resolved

            if isinstance(items, QuerySet):
                try:
                    if last is not None:
                        count = items.count(with_limit_and_skip=False)
                    else:
                        count = None
                except OperationFailure:
                    count = len(items)
            else:
                count = len(items)

            skip, limit = find_skip_and_limit(
                first=first, last=last, after=after, before=before, count=count
            )

            if isinstance(items, QuerySet):
                if limit:
                    _base_query: QuerySet = items.skip(skip)
                    items = _base_query.limit(limit)
                    has_next_page = len(_base_query.skip(skip + limit).only("id").limit(1)) != 0
                elif skip:
                    items = items.skip(skip)
            else:
                if limit:
                    _base_query = items
                    items = items[skip : skip + limit]
                    has_next_page = (
                        (skip + limit) < len(_base_query) if requires_page_info else False
                    )
                elif skip:
                    items = items[skip:]
            iterables = list(items)
            list_length = len(iterables)

        elif callable(getattr(self.model, "objects", None)):
            if "pk__in" in args:
                count = len(args["pk__in"])
                skip, limit = find_skip_and_limit(
                    first=first, last=last, after=after, before=before, count=count
                )
                if args["pk__in"]:
                    if limit:
                        args["pk__in"] = args["pk__in"][skip : skip + limit]
                    elif skip:
                        args["pk__in"] = args["pk__in"][skip:]
                    iterables = self.get_queryset(self.model, info, required_fields, **args)
                else:
                    iterables = []

                list_length = len(iterables)
                if isinstance(info, GraphQLResolveInfo):
                    if not info.context:
                        info = info._replace(context=Context())
                    info.context.queryset = self.get_queryset(
                        self.model, info, required_fields, **args
                    )
            elif (
                _root is None
                or args
                or isinstance(getattr(_root, field_name, []), MongoengineConnectionField)
            ):
                args_copy = self._build_args_copy(args)

                if first is None and last is None and before is None and after is None:
                    iterables = self.get_queryset(self.model, info, required_fields, **args)
                    list_length = len(iterables)
                    if isinstance(info, GraphQLResolveInfo):
                        if not info.context:
                            info = info._replace(context=Context())
                        info.context.queryset = self.get_queryset(
                            self.model, info, required_fields, **args
                        )
                else:
                    needs_count = last is not None or requires_page_info
                    if needs_count:
                        if PYMONGO_VERSION >= (3, 7):
                            if hasattr(self.model, "_meta") and "db_alias" in self.model._meta:
                                db = mongoengine.get_db(self.model._meta["db_alias"])
                            else:
                                db = mongoengine.get_db()
                            count = db[self.model._get_collection_name()].count_documents(
                                args_copy
                            )
                        else:
                            count = self.model.objects(args_copy).count()
                    if not needs_count or count != 0:
                        skip, limit = find_skip_and_limit(
                            first=first,
                            after=after,
                            last=last,
                            before=before,
                            count=count if needs_count else None,
                        )
                        iterables = self.get_queryset(
                            self.model, info, required_fields, skip, limit, **args
                        )
                        list_length = len(iterables)
                        if isinstance(info, GraphQLResolveInfo):
                            if not info.context:
                                info = info._replace(context=Context())
                            info.context.queryset = self.get_queryset(
                                self.model, info, required_fields, **args
                            )

        elif _root is not None:
            items = getattr(_root, field_name, [])
            count = len(items)
            skip, limit = find_skip_and_limit(
                first=first, last=last, after=after, before=before, count=count
            )
            if limit:
                _base_query = items
                items = items[skip : skip + limit]
                has_next_page = (skip + limit) < len(_base_query) if requires_page_info else False
            elif skip:
                items = items[skip:]
            iterables = items
            list_length = len(iterables)

        if requires_page_info and count:
            has_next_page = (
                True
                if (0 if limit is None else limit) + (0 if skip is None else skip) < count
                else False
            )
        has_previous_page = True if requires_page_info and skip else False

        connection = connection_from_iterables(
            edges=iterables,
            start_offset=skip,
            has_previous_page=has_previous_page,
            has_next_page=has_next_page,
            connection_type=self.type,
            edge_type=self.type.Edge,
            pageinfo_type=graphene.PageInfo,
        )
        connection.iterable = iterables
        connection.list_length = list_length
        return connection

    def chained_resolver(self, resolver, is_partial, root, info, **args):
        """Chain a user resolver with the default MongoEngine resolver.

        Calls the supplied *resolver* first. Depending on the return value:

        - None → falls through to default_resolver.
        - list (non-empty, non-DBRef) → returned as-is.
        - list of DBRef → re-queries via default_resolver.
        - QuerySet → its _query dict is merged into args and forwarded to
          default_resolver as resolved.
        - Promise → unwrapped and its value is returned.
        - Any other value → returned as-is.

        Before calling *resolver*, the queryset context (info.context.queryset)
        is populated for external consumers.

        Args:
            resolver (callable): The field's user-supplied or parent resolver.
            is_partial (bool): True when *resolver* is a functools.partial
                (i.e., a custom resolver was provided).
            root: The parent document instance.
            info: GraphQL resolve info object.
            **args: MongoEngine filter and Relay pagination arguments.

        Returns:
            Connection | list | Any: The resolved value for this connection field.
        """
        for key, value in dict(args).items():
            if value is None:
                del args[key]

        required_fields = self._collect_required_fields(info)
        args_copy = args.copy()

        if not bool(args) or not is_partial:
            if isinstance(self.model, mongoengine.Document) or isinstance(
                self.model, mongoengine.base.metaclasses.TopLevelDocumentMetaclass
            ):
                connection_fields = [
                    field
                    for field in self.fields
                    if isinstance(self.fields[field], MongoengineConnectionField)
                ]

                def filter_connection(x):
                    return any(
                        [
                            connection_fields.__contains__(x),
                            self._type._meta.non_filter_fields.__contains__(x),
                        ]
                    )

                filterable_args = tuple(
                    filterfalse(filter_connection, list(self.model._fields_ordered))
                )
                for arg_name, arg in args.copy().items():
                    if arg_name not in filterable_args + tuple(self.filter_args.keys()):
                        args_copy.pop(arg_name)
                if isinstance(info, GraphQLResolveInfo):
                    if not info.context:
                        info = info._replace(context=Context())
                    info.context.queryset = self.get_queryset(
                        self.model, info, required_fields, **args_copy
                    )

            resolved = resolver(root, info, **args)

            if resolved is not None:
                if isinstance(resolved, list):
                    if resolved == list():
                        return resolved
                    elif not isinstance(resolved[0], DBRef):
                        return resolved
                    else:
                        return self.default_resolver(root, info, required_fields, **args_copy)
                elif isinstance(resolved, QuerySet):
                    args.update(resolved._query)
                    args_copy = self._transform_qs_args(args, args.copy())
                    return self.default_resolver(
                        root, info, required_fields, resolved=resolved, **args_copy
                    )
                elif isinstance(resolved, Promise):
                    return resolved.value
                else:
                    return resolved

        return self.default_resolver(root, info, required_fields, **args)

    @classmethod
    def connection_resolver(cls, resolver, connection_type, root, info, **args):
        """Entry point called by graphene for every connection field resolution.

        Decodes any Relay global ID values on the root object before delegating
        to the chained resolver.  Wraps the resolver result in a Promise chain
        when the result is thenable (for compatibility with async-in-sync setups).

        Args:
            resolver (callable): The chained resolver produced by wrap_resolve.
            connection_type: The graphene connection type (or NonNull wrapper).
            root: The parent document instance, or None for top-level queries.
            info: GraphQL resolve info object.
            **args: GraphQL field arguments.

        Returns:
            Connection | Promise: The resolved Relay connection.
        """
        if root:
            for key, value in root.__dict__.items():
                if value:
                    try:
                        setattr(root, key, from_global_id(value)[1])
                    except Exception as error:
                        logging.debug("Exception Occurred: ", exc_info=error)
        iterable = resolver(root, info, **args)

        if isinstance(connection_type, graphene.NonNull):
            connection_type = connection_type.of_type

        on_resolve = partial(cls.resolve_connection, connection_type, args)

        if Promise.is_thenable(iterable):
            return Promise.resolve(iterable).then(on_resolve)

        return on_resolve(iterable)

    def wrap_resolve(self, parent_resolver):
        """Wrap the field's resolver to go through chained_resolver.

        Called by graphene when building the schema.  Composes the user resolver
        (or graphene's default attribute resolver) with chained_resolver
        and connection_resolver so the full resolution pipeline is applied.

        Args:
            parent_resolver (callable): The resolver provided by graphene (default
                attribute resolver or the one set on the field).

        Returns:
            callable: A partial that calls connection_resolver(chained_resolver)...), ...)
            for every incoming GraphQL request.
        """
        super_resolver = self.resolver or parent_resolver
        resolver = partial(
            self.chained_resolver, super_resolver, isinstance(super_resolver, partial)
        )
        return partial(self.connection_resolver, resolver, self.type)
