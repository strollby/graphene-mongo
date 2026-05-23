from collections.abc import Callable
from typing import Optional, Union

from bson import ObjectId
from graphene.utils.str_converters import to_snake_case
import mongoengine
from mongoengine import Document

from graphene_mongo.base.utils import ExecutorEnum, get_document, get_queried_union_types


class UnionFieldResolver:
    """Resolver factory for MongoEngine ``GenericReferenceField``.

    Handles lazy de-referencing of generic references (fields that can point to
    different document types). Identifies the concrete document type at resolve time,
    then fetches only the fields requested in the current GraphQL query.
    """

    @staticmethod
    def __reference_resolver_common(
        field, registry, executor: ExecutorEnum, root, *args, **kwargs
    ) -> Optional[Union[tuple[Document, set[str], ObjectId], Document]]:
        """Shared pre-fetch logic for both sync and async union resolvers.

        Reads the raw generic reference from the parent document, identifies the
        target document type, and determines which fields need to be fetched. Returns
        the already-loaded document if it has been fetched, or a tuple for the caller
        to query.

        Args:
            field: The MongoEngine ``GenericReferenceField`` instance being resolved.
            registry (Registry): Active type registry used to look up the target type.
            executor (ExecutorEnum): ``SYNC`` or ``ASYNC``.
            root: The parent MongoEngine document instance.
            *args: GraphQL positional args; ``args[0]`` must be the resolve info.
            **kwargs: GraphQL keyword args (unused here).

        Returns:
            ``Document`` — if the reference was already fetched (e.g. via ``select_related``).
            ``tuple[type, set[str], ObjectId]`` — ``(document_class, fields_to_fetch, pk)``
            if a DB query is required.
            ``Document(id=pk)`` — a stub instance if the type is not in the queried union.
            ``None`` — if the field value is empty / unset.
        """
        from graphene_mongo.base.converter import convert_mongoengine_field

        de_referenced = getattr(root, field.name or field.db_name)
        if not de_referenced:
            return None

        if isinstance(de_referenced, Document):
            return de_referenced

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
    def reference_resolver(field, registry, executor) -> Callable:
        """Return a synchronous resolver for a ``GenericReferenceField``.

        The returned resolver fetches the referenced document using
        ``model.objects.only(*fields).get(pk=pk)``.

        Args:
            field: The MongoEngine ``GenericReferenceField`` instance.
            registry (Registry): Active type registry.
            executor (ExecutorEnum): Should be ``ExecutorEnum.SYNC``.

        Returns:
            callable: ``resolver(root, *args, **kwargs) → Document | None``
        """
        def resolver(root, *args, **kwargs) -> Optional[Document]:
            result = UnionFieldResolver.__reference_resolver_common(
                field, registry, executor, root, *args, **kwargs
            )
            if not isinstance(result, tuple):
                return result
            document, only_fields, pk = result
            return document.objects.only(*only_fields).get(pk=pk)

        return resolver

    @staticmethod
    def reference_resolver_async(field, registry, executor) -> Callable:
        """Return an asynchronous resolver for a ``GenericReferenceField``.

        The returned coroutine fetches the referenced document using
        ``await model.aobjects.only(*fields).get(pk=pk)``.

        Args:
            field: The MongoEngine ``GenericReferenceField`` instance.
            registry (Registry): Active type registry.
            executor (ExecutorEnum): Should be ``ExecutorEnum.ASYNC``.

        Returns:
            callable: ``async resolver(root, *args, **kwargs) → Document | None``
        """
        async def resolver(root, *args, **kwargs) -> Optional[Document]:
            result = UnionFieldResolver.__reference_resolver_common(
                field, registry, executor, root, *args, **kwargs
            )
            if not isinstance(result, tuple):
                return result
            model, only_fields, document_id = result
            return await model.aobjects.only(*only_fields).get(pk=document_id)

        return resolver
