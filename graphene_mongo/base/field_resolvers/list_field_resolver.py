import asyncio
from asyncio import Future, Task
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, Union

import mongoengine
from bson import ObjectId
from graphene.utils.str_converters import to_snake_case
from mongoengine import Document
from mongoengine.base import LazyReference

from graphene_mongo.base.utils import ExecutorEnum, get_queried_union_types, get_document


class ListFieldResolver:
    """Resolver factory for MongoEngine ``ListField`` containing references.

    Efficiently resolves lists of ``GenericReferenceField`` entries by grouping
    references by their target document type, fetching each group in parallel
    (sync: ``ThreadPoolExecutor``; async: ``asyncio.gather``), and reassembling
    the results in the original order. Already-loaded ``Document`` instances
    (e.g. from ``select_related``) are passed through without additional DB queries.
    """

    @staticmethod
    def __get_reference_objects_common(
        registry,
        model,
        executor: ExecutorEnum,
        object_id_list: list[ObjectId],
        queried_fields: dict,
    ) -> tuple[Document, set[str], list[ObjectId]]:
        """Resolve the document class, field selection set, and IDs for a list of references.

        Converts ``model`` to its MongoEngine document class, determines which fields are
        queried (intersecting ``queried_fields`` with the document's field list), and appends
        any ``required_fields`` declared in Meta.

        Args:
            registry (Registry): Active type registry.
            model (str | type): MongoEngine document class or its class name string.
            executor (ExecutorEnum): ``SYNC`` or ``ASYNC``.
            object_id_list (list[ObjectId]): Primary keys to fetch.
            queried_fields (dict): Fields selected in the current GraphQL query.

        Returns:
            tuple[type, set[str], list[ObjectId]]:
                ``(document_class, fields_to_fetch, object_id_list)``
        """
        from graphene_mongo.base.converter import convert_mongoengine_field

        document = get_document(model)
        document_field = mongoengine.ReferenceField(document)
        document_field = convert_mongoengine_field(document_field, registry, executor)
        document_field_type = document_field.get_type().type
        _queried_fields = list()
        filter_args = list()
        if document_field_type._meta.filter_fields:
            for key, values in document_field_type._meta.filter_fields.items():
                for each in values:
                    filter_args.append(key + "__" + each)
        for each in queried_fields:
            item = to_snake_case(each)
            if item in document._fields_ordered + tuple(filter_args):
                _queried_fields.append(item)

        only_fields = set(list(document_field_type._meta.required_fields) + _queried_fields)
        return document, only_fields, object_id_list

    # ======================= DB CALLS =======================
    @staticmethod
    def __get_reference_objects(
        registry,
        model,
        executor: ExecutorEnum,
        object_id_list: list[ObjectId],
        queried_fields: dict,
    ):
        """Synchronously fetch a batch of documents by primary key.

        Args:
            registry (Registry): Active type registry.
            model (str | type): MongoEngine document class or its class name string.
            executor (ExecutorEnum): "SYNC".
            object_id_list (list[ObjectId]): Primary keys to fetch.
            queried_fields (dict): Fields selected in the current GraphQL query.

        Returns:
            QuerySet: Filtered QuerySet of matching documents with ``only`` projection.
        """
        document, only_fields, document_ids = ListFieldResolver.__get_reference_objects_common(
            registry, model, executor, object_id_list, queried_fields
        )
        return document.objects().only(*only_fields).filter(pk__in=document_ids)

    @staticmethod
    async def __get_reference_objects_async(
        registry,
        model,
        executor: ExecutorEnum,
        object_id_list: list[ObjectId],
        queried_fields: dict,
    ):
        """Asynchronously fetch a batch of documents by primary key.

        Args:
            registry (Registry): Active type registry.
            model (str | type): MongoEngine document class or its class name string.
            executor (ExecutorEnum): ``ASYNC``.
            object_id_list (list[ObjectId]): Primary keys to fetch.
            queried_fields (dict): Fields selected in the current GraphQL query.

        Returns:
            list[Document]: Fetched documents with ``only`` projection applied.
        """
        document, only_fields, document_ids = ListFieldResolver.__get_reference_objects_common(
            registry, model, executor, object_id_list, queried_fields
        )
        return await document.aobjects.only(*only_fields).filter(pk__in=document_ids).to_list()

    # ======================= DB CALLS: END =======================

    @staticmethod
    def __get_non_querying_object(model, object_id_list) -> list[Document]:
        """Return lightweight stub document instances without hitting the database.

        Used when the referenced type is not in the queried GraphQL fragment, so
        only the primary key is needed (no fields to fetch).

        Args:
            model (str | type): MongoEngine document class or its class name string.
            object_id_list (list[ObjectId]): Primary keys to create stubs for.

        Returns:
            list[Document]: Stub instances with ``pk`` set but no other fields loaded.
        """
        model = get_document(model)
        return [model(pk=each) for each in object_id_list]

    @staticmethod
    async def __get_non_querying_object_async(model, object_id_list) -> list[Document]:
        """Async wrapper around :meth:`__get_non_querying_object`; returns stubs without DB I/O.

        Args:
            model (str | type): MongoEngine document class or its class name string.
            object_id_list (list[ObjectId]): Primary keys to create stubs for.

        Returns:
            list[Document]: Stub instances with ``pk`` set but no other fields loaded.
        """
        return ListFieldResolver.__get_non_querying_object(model, object_id_list)

    @staticmethod
    def __build_results(
        result: list[Document],
        to_resolve_object_ids: list[ObjectId],
        already_resolved: dict[ObjectId, Document] = None,
    ) -> list[Document]:
        """Merge fetched batches and already-resolved documents back into original order.

        Args:
            result (list[Document]): Batches of documents returned by each fetch call.
                Each element is itself iterable (a QuerySet or list).
            to_resolve_object_ids (list[ObjectId]): Original ordered list of primary keys.
            already_resolved (dict[ObjectId, Document] | None): Documents already loaded
                (e.g. from "select_related`) keyed by their primary key.

        Returns:
            list[Document]: Documents ordered to match ``to_resolve_object_ids``.
        """
        result_object: dict[ObjectId, Document] = dict(already_resolved or {})
        for items in result:
            for item in items:
                result_object[item.id] = item
        return [result_object[each] for each in to_resolve_object_ids]

    # ======================= Main Logic =======================

    @staticmethod
    def __reference_resolver_common(
        field, registry, executor: ExecutorEnum, root, *args, **kwargs
    ) -> Optional[tuple[Union[list[Task], list[Document]], list[ObjectId]]]:
        """Shared dispatch logic for both sync and async list-reference resolvers.

        Iterates over the raw field value, separating already-loaded ``Document``
        instances from "LazyReference" entries and raw ``_cls``/``_ref`` dicts.
        Groups unresolved references by their document type, then either submits
        them to a "ThreadPoolExecutor" (sync) or creates "asyncio" tasks (async).

        Args:
            field: The MongoEngine ``ListField`` containing generic references.
            registry (Registry): Active type registry.
            executor (ExecutorEnum): ``SYNC`` or ``ASYNC`` — controls dispatch strategy.
            root: The parent MongoEngine document instance.
            *args: GraphQL positional args; ``args[0]`` must be the resolve info.
            **kwargs: GraphQL keyword args (unused here).

        Returns:
            ``tuple[list[Future | Task], list[ObjectId], dict[ObjectId, Document]]``
            for the caller to await / join, or ``None`` if the field is empty.
        """
        to_resolve = getattr(root, field.name or field.db_name)
        if not to_resolve:
            return None

        choice_to_resolve = dict()
        registry_string_map = registry._registry_string_map
        querying_union_types = get_queried_union_types(
            info=args[0], valid_gql_types=registry_string_map.keys()
        )
        to_resolve_models = dict()
        for each, queried_fields in querying_union_types.items():
            to_resolve_models[registry.get_type_for_model_string(each)] = queried_fields
        already_resolved: dict[ObjectId, Document] = {}
        to_resolve_object_ids: list[ObjectId] = list()
        for each in to_resolve:
            if isinstance(each, Document):
                already_resolved[each.pk] = each
                to_resolve_object_ids.append(each.pk)
            elif isinstance(each, LazyReference):
                to_resolve_object_ids.append(each.pk)
                model = each.document_type._class_name
                if model not in choice_to_resolve:
                    choice_to_resolve[model] = list()
                choice_to_resolve[model].append(each.pk)
            else:
                to_resolve_object_ids.append(each["_ref"].id)
                if each["_cls"] not in choice_to_resolve:
                    choice_to_resolve[each["_cls"]] = list()
                choice_to_resolve[each["_cls"]].append(each["_ref"].id)

        if executor == ExecutorEnum.SYNC:
            pool = ThreadPoolExecutor(5)
            futures: list[Future] = list()
            for model, object_id_list in choice_to_resolve.items():
                if model in to_resolve_models:
                    queried_fields = to_resolve_models[model]
                    futures.append(
                        pool.submit(
                            ListFieldResolver.__get_reference_objects,
                            *(registry, model, executor, object_id_list, queried_fields),
                        )
                    )
                else:
                    futures.append(
                        pool.submit(
                            ListFieldResolver.__get_non_querying_object,
                            *(model, object_id_list),
                        )
                    )
            result = [future.result() for future in as_completed(futures)]
            return result, to_resolve_object_ids, already_resolved
        else:
            loop = asyncio.get_event_loop()
            tasks: list[Task] = []
            for model, object_id_list in choice_to_resolve.items():
                if model in to_resolve_models:
                    queried_fields = to_resolve_models[model]
                    task = loop.create_task(
                        ListFieldResolver.__get_reference_objects_async(
                            registry,
                            model,
                            executor,
                            object_id_list,
                            queried_fields,
                        )
                    )
                else:
                    task = loop.create_task(
                        ListFieldResolver.__get_non_querying_object_async(model, object_id_list)
                    )
                tasks.append(task)
            return tasks, to_resolve_object_ids, already_resolved

    @staticmethod
    def reference_resolver(field, registry, executor) -> Callable:
        """Return a synchronous resolver for a list of generic references.

        Dispatches fetch jobs to a ``ThreadPoolExecutor``, then reassembles the
        results in the original order via :meth:`__build_results`.

        Args:
            field: The MongoEngine ``ListField`` containing generic references.
            registry (Registry): Active type registry.
            executor (ExecutorEnum): Should be ``ExecutorEnum.SYNC``.

        Returns:
            callable: ``resolver(root, *args, **kwargs) → list[Document] | None``
        """
        def resolver(root, *args, **kwargs) -> Optional[list[Document]]:
            resolver_result = ListFieldResolver.__reference_resolver_common(
                field, registry, executor, root, *args, **kwargs
            )
            if not isinstance(resolver_result, tuple):
                return resolver_result
            result, to_resolve_object_ids, already_resolved = resolver_result
            return ListFieldResolver.__build_results(result, to_resolve_object_ids, already_resolved)

        return resolver

    @staticmethod
    def reference_resolver_async(field, registry, executor) -> Callable:
        """Return an asynchronous resolver for a list of generic references.

        Awaits all ``asyncio`` tasks via ``asyncio.gather``, then reassembles the
        results in the original order via :meth:`__build_results`.

        Args:
            field: The MongoEngine ``ListField`` containing generic references.
            registry (Registry): Active type registry.
            executor (ExecutorEnum): Should be ``ExecutorEnum.ASYNC``.

        Returns:
            callable: ``async resolver(root, *args, **kwargs) → list[Document] | None``
        """
        async def resolver(root, *args, **kwargs) -> Optional[list[Document]]:
            resolver_result = ListFieldResolver.__reference_resolver_common(
                field, registry, executor, root, *args, **kwargs
            )
            if not isinstance(resolver_result, tuple):
                return resolver_result
            tasks, to_resolve_object_ids, already_resolved = resolver_result
            result: list[Document] = await asyncio.gather(*tasks)
            return ListFieldResolver.__build_results(result, to_resolve_object_ids, already_resolved)

        return resolver

    # ======================= Main Logic: END =======================
