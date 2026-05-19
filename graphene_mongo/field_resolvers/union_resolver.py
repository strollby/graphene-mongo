from collections.abc import Callable
from typing import Optional, Union

from bson import ObjectId
from graphene.utils.str_converters import to_snake_case
import mongoengine
from mongoengine import Document
from mongoengine.base import LazyReference

from graphene_mongo.utils import ExecutorEnum, get_dataloader, get_document, get_queried_union_types


class UnionFieldResolver:
    @staticmethod
    def __reference_resolver_common(
        field, registry, executor: ExecutorEnum, root, *args, **kwargs
    ) -> Optional[Union[tuple[Document, set[str], ObjectId], Document]]:
        from graphene_mongo.converter import convert_mongoengine_field

        de_referenced: LazyReference = getattr(root, field.name or field.db_name)
        if not de_referenced:
            return None

        document = get_document(de_referenced.document_type)
        document_id = de_referenced.id
        document_field = mongoengine.ReferenceField(document)
        document_field = convert_mongoengine_field(document_field, registry, executor=executor)
        _type = document_field.get_type().type
        filter_args = list()
        if _type._meta.filter_fields:
            for key, values in _type._meta.filter_fields.items():
                for each in values:
                    filter_args.append(key + "__" + each)

        registry_string_map = registry._registry_string_map
        querying_union_types = get_queried_union_types(
            info=args[0], valid_gql_types=registry_string_map.keys()
        )

        if _type.__name__ in querying_union_types:
            queried_fields = list()
            for each in querying_union_types[_type._meta.name].keys():
                item = to_snake_case(each)
                if item in document._fields_ordered + tuple(filter_args):
                    queried_fields.append(item)

            only_fields = set(list(_type._meta.required_fields) + queried_fields)

            return document, only_fields, document_id

        return document(id=document_id)

    @staticmethod
    def resolver(field, registry, executor) -> Callable:
        def resolver(root, *args, **kwargs) -> Optional[Document]:
            resolver_fun = UnionFieldResolver.__reference_resolver_common
            result = resolver_fun(field, registry, executor, root, *args, **kwargs)
            if not isinstance(result, tuple):
                return result
            document, only_fields, pk = result
            return document.objects.only(*only_fields).get(pk=pk)

        return resolver

    @staticmethod
    def resolver_async(field, registry, executor) -> Callable:
        async def resolver(root, *args, **kwargs) -> Optional[Document]:
            resolver_fun = UnionFieldResolver.__reference_resolver_common
            result = resolver_fun(field, registry, executor, root, *args, **kwargs)
            if not isinstance(result, tuple):
                return result
            model, only_fields, id = result
            return (
                await get_dataloader(info=args[0])
                .model(model_class=model, projections=only_fields)
                .load(id)
            )

        return resolver
