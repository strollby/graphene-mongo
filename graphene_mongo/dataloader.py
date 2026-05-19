"""
MongoEngine DataLoader for GraphQL resolution.

Usage:
    # ====================== Type level ======================

    class UserType(AsyncMongoengineObjectType):
        class Meta:
            model = User

        @classmethod
        async def dataloader_resolver(
            cls, info: GraphQLResolveInfo, ids: list[ObjectId], projections: list[str] | None = None
        ):
            docs = QS(User, auto_deference=False).filter(id__in=ids)
            if projections:
                docs = docs.only(*projections)
            return await docs.to_list()

    # ====================== Field Level ======================
    from graphene_mongo.utils import get_dataloader

    loader = get_dataloader(info)

    # Single fetch
    user = await loader.model(User, projections).get(user_id)

    # Pre-load in bulk (e.g. in a resolver that already has many ids)
    await loader.model(Post, projections).load_many([id1, id2, id3])
    post = await loader.model(Post).get(id1)  # served from cache

    # This attached the loader to your GraphQL context so it's
    # shared across all resolvers in a single request, giving you automatic
    # N+1 batching.
"""

from __future__ import annotations

from typing import Generic, Type, TypeVar

from aiodataloader import DataLoader
from bson import ObjectId
from graphql import GraphQLResolveInfo
from mongoengine import Document

T = TypeVar("T", bound=Document)


class ModelLoader(DataLoader, Generic[T]):
    """
    A per-model DataLoader that batches `.get(id)` calls into a single
    MongoDB query per tick of the event loop.
    """

    def __init__(self, model: Type[T], info: GraphQLResolveInfo, projections: set[str], **kwargs):
        super().__init__(cache=True, **kwargs)
        self._info = info
        self._model = model
        self._projections: set[str] = projections

        from .registry import get_global_async_registry
        from .types_async import AsyncMongoengineObjectType

        registry = get_global_async_registry()
        self._gql_type: AsyncMongoengineObjectType = registry.get_type_for_document_model(model)
        if self._gql_type is None:
            raise NotImplementedError(f"Please define AsyncMongoengineObjectType for {model}")

    async def batch_load_fn(self, keys: list[str]) -> list[T | None]:
        """
        Called once per event-loop tick with all ids accumulated so far.
        Executes a single `filter(id__in=...)` query and maps results back
        to the original key order (DataLoader requires 1-to-1 ordering).
        """
        # Normalise to ObjectId so MongoEngine is happy either way
        object_ids: list[ObjectId] = []
        for k in keys:
            try:
                object_ids.append(ObjectId(k) if not isinstance(k, ObjectId) else k)
            except Exception:
                object_ids.append(k)  # let Mongo surface the error naturally

        docs = await self._gql_type.dataloader_resolver(
            info=self._info,
            ids=object_ids,
            projections=list(self._projections) if self._projections else None,
        )

        id_map: dict[str, T] = {str(doc.id): doc for doc in docs}

        # Preserve key order; missing ids resolve to None
        return [id_map.get(str(k)) for k in keys]


class MongoDataLoader:
    """
    Request-scoped container for per-model DataLoaders.
    """

    def __init__(self, info: GraphQLResolveInfo):
        self._info = info
        self._loaders: dict[tuple[type, frozenset[str]], ModelLoader] = {}

    def model(self, model_class: Type[T], projections: set[str]) -> ModelLoader[T]:
        """
        Returns (or creates) the DataLoader for the given MongoEngine model.
        Loaders are cached per model class for the lifetime of this object.
        """
        requested_projections = frozenset(projections)
        key = (model_class, requested_projections)

        if self._loaders.get(key):
            return self._loaders[key]

        # Trying to find a loader which has superset projections
        existing_key = next((k for k in self._loaders if k[0] == model_class), None)
        if existing_key:
            existing_loader = self._loaders[existing_key]
            existing_projections = existing_key[1]
            if projections.issubset(existing_projections):
                # reuse old loader as its projections are subset
                return existing_loader

        self._loaders[key] = ModelLoader(
            model=model_class, info=self._info, projections=set(requested_projections)
        )
        return self._loaders[key]
