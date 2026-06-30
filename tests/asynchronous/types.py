from graphene.types.union import Union

from graphene_mongo.asynchronous.types import (
    AsyncMongoengineInterfaceType,
    AsyncMongoengineObjectType,
)
from graphene_mongo.base.registry import Registry
from graphene_mongo.base.utils import ExecutorEnum

from .. import models
from ..types import ArticleInput, EditorInput  # noqa: F401 — re-exported for convenience

# Isolated registry so these non-relay types don't overwrite the relay nodes in
# the global async registry used by tests/asynchronous/nodes.py.
local_async_registry = Registry(executor=ExecutorEnum.ASYNC)


class PublisherAsyncType(AsyncMongoengineObjectType):
    class Meta:
        model = models.Publisher
        registry = local_async_registry


class EditorAsyncType(AsyncMongoengineObjectType):
    class Meta:
        model = models.Editor
        registry = local_async_registry


class ArticleAsyncType(AsyncMongoengineObjectType):
    class Meta:
        model = models.Article
        registry = local_async_registry


class EmbeddedArticleAsyncType(AsyncMongoengineObjectType):
    class Meta:
        model = models.EmbeddedArticle
        registry = local_async_registry


class PlayerAsyncType(AsyncMongoengineObjectType):
    class Meta:
        model = models.Player
        registry = local_async_registry


class ReporterAsyncType(AsyncMongoengineObjectType):
    class Meta:
        model = models.Reporter
        registry = local_async_registry


class ProfessorMetadataAsyncType(AsyncMongoengineObjectType):
    class Meta:
        model = models.ProfessorMetadata
        registry = local_async_registry


class ProfessorVectorAsyncType(AsyncMongoengineObjectType):
    class Meta:
        model = models.ProfessorVector
        registry = local_async_registry


class CellTowerAsyncType(AsyncMongoengineObjectType):
    class Meta:
        model = models.CellTower
        registry = local_async_registry


class ParentAsyncInterface(AsyncMongoengineInterfaceType):
    class Meta:
        model = models.Parent
        registry = local_async_registry
        exclude_fields = ["loc"]


class ChildAsyncType(AsyncMongoengineObjectType):
    class Meta:
        model = models.Child
        registry = local_async_registry
        interfaces = (ParentAsyncInterface,)


class AnotherChildAsyncType(AsyncMongoengineObjectType):
    class Meta:
        model = models.AnotherChild
        registry = local_async_registry
        interfaces = (ParentAsyncInterface,)


class ChildAsyncUnionType(Union):
    class Meta:
        types = (ChildAsyncType, AnotherChildAsyncType)
        interfaces = (ParentAsyncInterface,)


# Deep select_related stress-test types
class DeepL10AsyncType(AsyncMongoengineObjectType):
    class Meta:
        model = models.DeepL10
        registry = local_async_registry


class DeepL9AsyncType(AsyncMongoengineObjectType):
    class Meta:
        model = models.DeepL9
        registry = local_async_registry


class DeepL8AsyncType(AsyncMongoengineObjectType):
    class Meta:
        model = models.DeepL8
        registry = local_async_registry


class DeepL7AsyncType(AsyncMongoengineObjectType):
    class Meta:
        model = models.DeepL7
        registry = local_async_registry


class DeepL6AsyncType(AsyncMongoengineObjectType):
    class Meta:
        model = models.DeepL6
        registry = local_async_registry


class DeepL5AsyncType(AsyncMongoengineObjectType):
    class Meta:
        model = models.DeepL5
        registry = local_async_registry


class DeepL4AsyncType(AsyncMongoengineObjectType):
    class Meta:
        model = models.DeepL4
        registry = local_async_registry


class DeepL3AsyncType(AsyncMongoengineObjectType):
    class Meta:
        model = models.DeepL3
        registry = local_async_registry


class DeepL2AsyncType(AsyncMongoengineObjectType):
    class Meta:
        model = models.DeepL2
        registry = local_async_registry


class DeepL1AsyncType(AsyncMongoengineObjectType):
    class Meta:
        model = models.DeepL1
        registry = local_async_registry
