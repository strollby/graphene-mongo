from __future__ import absolute_import

import bson
import graphene
import mongoengine
import pymongo
from bson import ObjectId
from graphene import ConnectionField, Context, Int
from graphene.utils.str_converters import to_snake_case
from graphql import GraphQLResolveInfo
from graphql_relay import cursor_to_offset, from_global_id
from mongoengine import QuerySet
from pymongo.errors import OperationFailure

from .utils import connection_from_iterables, find_skip_and_limit, has_page_count
from ...fields_async import (
    AsyncMongoengineConnectionField,
)
from ...utils import (
    has_page_info,
    sync_to_async,
)

PYMONGO_VERSION = tuple(pymongo.version_tuple[:2])


class AsyncMongoenginePaginationField(AsyncMongoengineConnectionField):
    def __init__(self, type, *args, **kwargs):
        kwargs.setdefault("offset", Int())
        kwargs.setdefault("limit", Int())
        super(AsyncMongoenginePaginationField, self).__init__(type, *args, **kwargs)

    @property
    def type(self):
        from .types_pagination_async import AsyncMongoenginePaginationObjectType

        _type = super(ConnectionField, self).type
        assert issubclass(
            _type, AsyncMongoenginePaginationObjectType
        ), "AsyncMongoengineConnectionField only accepts AsyncMongoenginePaginationObjectType types"
        assert _type._meta.connection, "The type {} doesn't have a connection".format(
            _type.__name__
        )
        return _type._meta.connection

    async def default_resolver(self, _root, info, required_fields=None, resolved=None, **args):
        if required_fields is None:
            required_fields = list()
        args.update(info.variable_values)  # Pagination Logic
        args = args or {}
        for key, value in dict(args).items():
            if value is None:
                del args[key]
        if _root is not None and not resolved:
            field_name = to_snake_case(info.field_name)
            if not hasattr(_root, "_fields_ordered"):
                if isinstance(getattr(_root, field_name, []), list):
                    args["pk__in"] = [r.id for r in getattr(_root, field_name, [])]
            elif field_name in _root._fields_ordered and not (
                isinstance(_root._fields[field_name].field, mongoengine.EmbeddedDocumentField)
                or isinstance(
                    _root._fields[field_name].field,
                    mongoengine.GenericEmbeddedDocumentField,
                )
            ):
                if getattr(_root, field_name, []) is not None:
                    args["pk__in"] = [r.id for r in getattr(_root, field_name, [])]

        _id = args.pop("id", None)

        if _id is not None:
            args["pk"] = from_global_id(_id)[-1]
        iterables = []
        list_length = 0
        skip = 0
        count = 0
        limit = None
        reverse = False
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

        # Pagination Logic
        page_offset = args.pop("offset", None)
        page_limit = args.pop("limit", None)

        page_count = None
        requires_page_count = has_page_count(info)

        if requires_page_count and page_offset is None:
            raise ValueError("Page count requires offset pagination")

        if page_offset is not None:
            if after or before:
                raise ValueError("Offset pagination does not support cursor based paging")
            if first:
                raise ValueError("first argument not allowed in offset pagination")
            if last:
                raise ValueError("last argument not allowed in offset pagination")
            if page_limit is None:
                raise ValueError("limit argument is required in offset pagination")

        # End of Pagination Logic

        if resolved is not None:
            items = resolved

            if isinstance(items, QuerySet):
                try:
                    if (
                        last is not None and after is not None
                    ) or requires_page_count:  # Pagination Logic
                        count = await sync_to_async(items.count)(with_limit_and_skip=False)
                    else:
                        count = None
                except OperationFailure:
                    count = await sync_to_async(len)(items)
            else:
                count = len(items)

            skip, limit, reverse = find_skip_and_limit(
                first=first,
                last=last,
                after=after,
                before=before,
                page_offset=page_offset,
                page_limit=page_limit,
                count=count,
            )

            if isinstance(items, QuerySet):
                if limit:
                    _base_query: QuerySet = (
                        await sync_to_async(items.order_by("-pk").skip)(skip)
                        if reverse
                        else await sync_to_async(items.skip)(skip)
                    )
                    items = await sync_to_async(_base_query.limit)(limit)
                    has_next_page = (
                        (await sync_to_async(len)(_base_query.skip(limit).only("id").limit(1)) != 0)
                        if requires_page_info
                        else False
                    )
                elif skip:
                    items = await sync_to_async(items.skip)(skip)
            else:
                if limit:
                    if reverse:
                        _base_query = items[::-1]
                        items = _base_query[skip : skip + limit]
                    else:
                        _base_query = items
                        items = items[skip : skip + limit]
                    has_next_page = (
                        (skip + limit) < len(_base_query) if requires_page_info else False
                    )
                elif skip:
                    items = items[skip:]
            iterables = await sync_to_async(list)(items)
            list_length = len(iterables)

        elif callable(getattr(self.model, "objects", None)):
            if (
                _root is None
                or args
                or isinstance(getattr(_root, field_name, []), AsyncMongoengineConnectionField)
            ):
                args_copy = args.copy()
                for key in args.copy():
                    if key not in self.model._fields_ordered:
                        args_copy.pop(key)
                    elif (
                        isinstance(getattr(self.model, key), mongoengine.fields.ReferenceField)
                        or isinstance(
                            getattr(self.model, key),
                            mongoengine.fields.GenericReferenceField,
                        )
                        or isinstance(
                            getattr(self.model, key),
                            mongoengine.fields.LazyReferenceField,
                        )
                        or isinstance(
                            getattr(self.model, key),
                            mongoengine.fields.CachedReferenceField,
                        )
                    ):
                        if not isinstance(args_copy[key], ObjectId):
                            _from_global_id = from_global_id(args_copy[key])[1]
                            if bson.objectid.ObjectId.is_valid(_from_global_id):
                                args_copy[key] = ObjectId(_from_global_id)
                            else:
                                args_copy[key] = _from_global_id
                    elif isinstance(getattr(self.model, key), mongoengine.fields.EnumField):
                        if getattr(args_copy[key], "value", None):
                            args_copy[key] = args_copy[key].value

                if PYMONGO_VERSION >= (3, 7):
                    count = await sync_to_async(
                        (mongoengine.get_db()[self.model._get_collection_name()]).count_documents
                    )(args_copy)
                else:
                    count = await sync_to_async(self.model.objects(args_copy).count)()
                if count != 0:
                    skip, limit, reverse = find_skip_and_limit(
                        first=first,
                        after=after,
                        last=last,
                        before=before,
                        page_offset=page_offset,
                        page_limit=page_limit,
                        count=count,
                    )
                    iterables = self.get_queryset(
                        self.model, info, required_fields, skip, limit, reverse, **args
                    )
                    iterables = await sync_to_async(list)(iterables)
                    list_length = len(iterables)
                    if isinstance(info, GraphQLResolveInfo):
                        if not info.context:
                            info = info._replace(context=Context())
                        info.context.queryset = self.get_queryset(
                            self.model, info, required_fields, **args
                        )

            elif "pk__in" in args and args["pk__in"]:
                count = len(args["pk__in"])
                skip, limit, reverse = find_skip_and_limit(
                    first=first,
                    last=last,
                    after=after,
                    before=before,
                    page_offset=page_offset,
                    page_limit=page_limit,
                    count=count,
                )
                if limit:
                    if reverse:
                        args["pk__in"] = args["pk__in"][::-1][skip : skip + limit]
                    else:
                        args["pk__in"] = args["pk__in"][skip : skip + limit]
                elif skip:
                    args["pk__in"] = args["pk__in"][skip:]
                iterables = self.get_queryset(self.model, info, required_fields, **args)
                iterables = await sync_to_async(list)(iterables)
                list_length = len(iterables)
                if isinstance(info, GraphQLResolveInfo):
                    if not info.context:
                        info = info._replace(context=Context())
                    info.context.queryset = self.get_queryset(
                        self.model, info, required_fields, **args
                    )

        elif _root is not None:
            field_name = to_snake_case(info.field_name)
            items = getattr(_root, field_name, [])
            count = len(items)
            skip, limit, reverse = find_skip_and_limit(
                first=first,
                last=last,
                after=after,
                before=before,
                page_offset=page_offset,
                page_limit=page_limit,
                count=count,
            )
            if limit:
                if reverse:
                    _base_query = items[::-1]
                    items = _base_query[skip : skip + limit]
                else:
                    _base_query = items
                    items = items[skip : skip + limit]
                has_next_page = (skip + limit) < len(_base_query) if requires_page_info else False
            elif skip:
                items = items[skip:]
            iterables = items
            iterables = await sync_to_async(list)(iterables)
            list_length = len(iterables)

        if requires_page_info and count:
            has_next_page = (
                True
                if (0 if limit is None else limit) + (0 if skip is None else skip) < count
                else False
            )
        has_previous_page = True if requires_page_info and skip else False

        # Pagination Logic
        if requires_page_count:
            page_count = (count if count is not None else 0) // page_limit
        # Pagination Logic End

        if reverse:
            iterables = await sync_to_async(list)(iterables)
            iterables.reverse()
            skip = limit

        connection = connection_from_iterables(
            edges=iterables,
            start_offset=skip,
            has_previous_page=has_previous_page,
            has_next_page=has_next_page,
            connection_type=self.type,
            edge_type=self.type.Edge,
            pageinfo_type=graphene.PageInfo,
            page_count=page_count,  # Pagination Logic
        )
        connection.iterable = iterables
        connection.list_length = list_length
        return connection
