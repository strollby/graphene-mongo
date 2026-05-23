from collections.abc import Callable
from typing import Optional, Union

from bson import ObjectId
from graphene.utils.str_converters import to_snake_case
from mongoengine import Document, ReferenceField

from graphene_mongo.base.utils import ExecutorEnum, get_query_fields


class DynamicReferenceFieldResolver:
    """Resolver factory for MongoEngine ReferenceField and EmbeddedDocumentField.

    Handles lazy de-referencing efficiently: if select_related has already
    loaded the referenced document it is returned immediately without a DB round
    trip. Otherwise a targeted query is issued fetching only the fields selected
    in the current GraphQL query (plus any required_fields declared in Meta).
    """

    @staticmethod
    def __reference_resolver_common(
        field, registry, executor: ExecutorEnum, root, *args, **kwargs
    ) -> Optional[Union[tuple[Document, set[str], ObjectId], Document]]:
        """Shared pre-fetch logic for both sync and async resolvers.

        Reads the raw value from the parent document, determines which fields
        need to be fetched, and either returns the already-loaded document or
        a (document_class, fields_to_fetch, pk) tuple for the caller to query.

        Args:
            field: The MongoEngine ReferenceField instance being resolved.
            registry (Registry): Active type registry used to look up the target type.
            executor (ExecutorEnum): SYNC or ASYNC.
            root: The parent MongoEngine document instance.
            *args: GraphQL positional args; args[0] must be the resolve info.
            **kwargs: GraphQL keyword args (unused here).

        Returns:
            Document — if the reference was already fetched by select_related.
            tuple[type, set[str], ObjectId] — (document_class, fields_to_fetch, pk)
            if a DB query is required.
            None — if the field value is empty / unset.
        """
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
            return document  # Already fetched by select_related

        document_id = (
            document.id
            if isinstance(field, ReferenceField)
            else getattr(root, field.name or field.db_name)
        )
        return field.document_type, fields_to_fetch, document_id

    @staticmethod
    def reference_resolver(field, registry, executor) -> Callable:
        """Return a synchronous resolver for a ReferenceField.

        The returned resolver fetches the referenced document using
        model.objects.only(*fields).get(pk=pk).

        Args:
            field: The MongoEngine ReferenceField instance.
            registry (Registry): Active type registry.
            executor (ExecutorEnum): Should be ExecutorEnum.SYNC.

        Returns:
            callable: resolver(root, *args, **kwargs) → Document | None
        """
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
        """Return an asynchronous resolver for a ReferenceField.

        The returned coroutine fetches the referenced document using
        await model.aobjects.only(*fields).get(pk=pk).

        Args:
            field: The MongoEngine ReferenceField instance.
            registry (Registry): Active type registry.
            executor (ExecutorEnum): Should be ExecutorEnum.ASYNC.

        Returns:
            callable: async resolver(root, *args, **kwargs) → Document | None
        """
        async def resolver(root, *args, **kwargs) -> Optional[Document]:
            result = DynamicReferenceFieldResolver.__reference_resolver_common(
                field, registry, executor, root, *args, **kwargs
            )
            if not isinstance(result, tuple):
                return result
            model, only_fields, document_id = result
            return await model.aobjects.only(*only_fields).get(pk=document_id)

        return resolver
