from collections.abc import Callable
from typing import Optional, Union

from bson import ObjectId
from graphene.utils.str_converters import to_snake_case
from mongoengine import Document, ReferenceField

from graphene_mongo.base.utils import ExecutorEnum, get_query_fields


class DynamicReferenceFieldResolver:
    """Fallback resolver for ReferenceField when select_related has not pre-loaded the document.

    select_related only resolves references that are directly reachable from the root
    queryset. Nested references (e.g. editor.company) and references inside custom
    get_queryset implementations may return LazyReference objects instead of loaded
    Documents. This resolver detects that case and issues a targeted query fetching
    only the fields selected in the current GraphQL query.
    """

    @staticmethod
    def __reference_resolver_common(
        field, registry, executor: ExecutorEnum, root, *args, **kwargs
    ) -> Optional[Union[tuple[Document, set[str], ObjectId], Document]]:
        document = root._data.get(field.name or field.db_name, None)
        if not document:
            return None

        queried_fields = list()
        _type = registry.get_type_for_model(field.document_type)
        filter_args = list()
        if _type._meta.filter_fields:
            for key, values in _type._meta.filter_fields.items():
                for each in values:
                    filter_args.append(key + "__" + each)
        for each in get_query_fields(args[0]).keys():
            item = to_snake_case(each)
            if item in field.document_type._fields_ordered + tuple(filter_args):
                queried_fields.append(item)

        fields_to_fetch = set(list(_type._meta.required_fields) + queried_fields)
        if isinstance(document, field.document_type):
            return document

        document_id = (
            document.id
            if isinstance(field, ReferenceField)
            else getattr(root, field.name or field.db_name)
        )
        return field.document_type, fields_to_fetch, document_id

    @staticmethod
    def reference_resolver(field, registry, executor) -> Callable:
        """Return a synchronous resolver for a ReferenceField."""
        def resolver(root, *args, **kwargs) -> Optional[Document]:
            result = DynamicReferenceFieldResolver.__reference_resolver_common(
                field, registry, executor, root, *args, **kwargs
            )
            if not isinstance(result, tuple):
                return result
            document, only_fields, pk = result
            return document.objects.only(*only_fields).get(pk=pk)

        return resolver

    @staticmethod
    def reference_resolver_async(field, registry, executor) -> Callable:
        """Return an asynchronous resolver for a ReferenceField."""
        async def resolver(root, *args, **kwargs) -> Optional[Document]:
            result = DynamicReferenceFieldResolver.__reference_resolver_common(
                field, registry, executor, root, *args, **kwargs
            )
            if not isinstance(result, tuple):
                return result
            model, only_fields, document_id = result
            return await model.aobjects.only(*only_fields).get(pk=document_id)

        return resolver