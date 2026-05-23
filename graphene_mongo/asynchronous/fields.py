from functools import partial
from itertools import filterfalse
from typing import Coroutine

import graphene
from bson import DBRef
from graphene import Context
from graphene.relay import ConnectionField
from graphql import GraphQLResolveInfo
from graphql_relay import cursor_to_offset, from_global_id
import mongoengine
from mongoengine import AsyncQuerySet, QuerySet
from promise import Promise
from pymongo.errors import OperationFailure

from ..synchronous.fields import MongoengineConnectionField
from ..base.registry import get_global_async_registry
from ..base.utils import (
    ExecutorEnum,
    connection_from_iterables,
    find_skip_and_limit,
    has_page_info,
)


class AsyncMongoengineConnectionField(MongoengineConnectionField):
    @property
    def executor(self):
        return ExecutorEnum.ASYNC

    @property
    def type(self):
        from .types import AsyncMongoengineObjectType

        _type = super(ConnectionField, self).type
        assert issubclass(_type, AsyncMongoengineObjectType), (
            "AsyncMongoengineConnectionField only accepts AsyncMongoengineObjectType types"
        )
        assert _type._meta.connection, "The type {} doesn't have a connection".format(
            _type.__name__
        )
        return _type._meta.connection

    @property
    def registry(self):
        return getattr(self.node_type._meta, "registry", get_global_async_registry())

    def _qs_accessor(self, model):
        return model.aobjects

    def get_queryset(
        self, model, info, required_fields=None, skip=None, limit=None, **args
    ) -> AsyncQuerySet:
        if required_fields is None:
            required_fields = list()
        if args:
            self._hydrate_args(args)
        if self._get_queryset:
            queryset_or_filters = self._get_queryset(model, info, **args)
            if isinstance(queryset_or_filters, mongoengine.AsyncQuerySet):
                return queryset_or_filters
            elif isinstance(queryset_or_filters, mongoengine.QuerySet):
                raise TypeError(
                    "AsyncMongoengineConnectionField only accepts AsyncQuerySet in get_queryset(...)"
                )
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

    async def default_resolver(self, _root, info, required_fields=None, resolved=None, **args):
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

            if isinstance(items, AsyncQuerySet):
                try:
                    if last is not None:
                        count = await items.count(with_limit_and_skip=False)
                    else:
                        count = None
                except OperationFailure:
                    count = len(await items.to_list())
            else:
                count = len(items)

            skip, limit = find_skip_and_limit(
                first=first, last=last, after=after, before=before, count=count
            )

            if isinstance(items, AsyncQuerySet):
                if limit:
                    _base_query: AsyncQuerySet = await items.skip(skip)
                    items = await _base_query.limit(limit)
                    has_next_page = (
                        (
                            len(
                                await _base_query.skip(skip + limit).only("id").limit(1).to_list()
                            )
                            != 0
                        )
                        if requires_page_info
                        else False
                    )
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
            iterables = await items.to_list() if isinstance(items, AsyncQuerySet) else list(items)
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
                    iterables = await self.get_queryset(
                        self.model, info, required_fields, **args
                    ).to_list()
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
                or isinstance(getattr(_root, field_name, []), AsyncMongoengineConnectionField)
            ):
                args_copy = self._build_args_copy(args)

                if first is None and last is None and before is None and after is None:
                    iterables = await self.get_queryset(
                        self.model, info, required_fields, **args
                    ).to_list()
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
                        count = await self.model.aobjects(**args_copy).count()
                    if not needs_count or count != 0:
                        skip, limit = find_skip_and_limit(
                            first=first,
                            after=after,
                            last=last,
                            before=before,
                            count=count if needs_count else None,
                        )
                        iterables = await self.get_queryset(
                            self.model, info, required_fields, skip, limit, **args
                        ).to_list()
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
            iterables = await items.to_list()
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

    async def chained_resolver(self, resolver, is_partial, root, info, **args):
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
                    if isinstance(self.fields[field], AsyncMongoengineConnectionField)
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
            if isinstance(resolved, Coroutine):
                resolved = await resolved
            if resolved is not None:
                if isinstance(resolved, list):
                    if resolved == list():
                        return resolved
                    elif not isinstance(resolved[0], DBRef):
                        return resolved
                    else:
                        return await self.default_resolver(
                            root, info, required_fields, **args_copy
                        )
                elif isinstance(resolved, QuerySet):
                    args.update(resolved._query)
                    args_copy = self._transform_qs_args(args, args.copy())
                    return await self.default_resolver(
                        root, info, required_fields, resolved=resolved, **args_copy
                    )
                elif isinstance(resolved, Promise):
                    return resolved.value
                else:
                    return await resolved

        return await self.default_resolver(root, info, required_fields, **args)

    @classmethod
    async def connection_resolver(cls, resolver, connection_type, root, info, **args):
        if root:
            for key, value in root.__dict__.items():
                if value:
                    try:
                        setattr(root, key, from_global_id(value)[1])
                    except Exception:
                        pass

        iterable = await resolver(root=root, info=info, **args)

        if isinstance(connection_type, graphene.NonNull):
            connection_type = connection_type.of_type
        on_resolve = partial(cls.resolve_connection, connection_type, args)
        if Promise.is_thenable(iterable):
            iterable = Promise.resolve(iterable).then(on_resolve).value
        return on_resolve(iterable)
