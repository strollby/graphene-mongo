import graphene
from graphene.relay import Node

from .. import models
from .. import types  # noqa: F401
from ..models import ProfessorMetadata
from graphene_mongo.asynchronous.types import AsyncMongoengineObjectType


class PublisherAsyncNode(AsyncMongoengineObjectType):
    legal_name = graphene.String()
    bad_field = graphene.String()

    class Meta:
        model = models.Publisher
        only_fields = ("id", "name")
        interfaces = (Node,)


class ArticleAsyncNode(AsyncMongoengineObjectType):
    class Meta:
        model = models.Article
        interfaces = (Node,)


class EditorAsyncNode(AsyncMongoengineObjectType):
    class Meta:
        model = models.Editor
        interfaces = (Node,)


class EmbeddedArticleAsyncNode(AsyncMongoengineObjectType):
    class Meta:
        model = models.EmbeddedArticle
        interfaces = (Node,)


class PlayerAsyncNode(AsyncMongoengineObjectType):
    class Meta:
        model = models.Player
        interfaces = (Node,)
        filter_fields = {"first_name": ["istartswith", "in"]}


class ReporterAsyncNode(AsyncMongoengineObjectType):
    class Meta:
        model = models.Reporter
        interfaces = (Node,)


class ParentAsyncNode(AsyncMongoengineObjectType):
    class Meta:
        model = models.Parent
        interfaces = (Node,)


class ChildAsyncNode(AsyncMongoengineObjectType):
    class Meta:
        model = models.Child
        interfaces = (Node,)


class ChildRegisteredBeforeAsyncNode(AsyncMongoengineObjectType):
    class Meta:
        model = models.ChildRegisteredBefore
        interfaces = (Node,)


class ChildRegisteredAfterAsyncNode(AsyncMongoengineObjectType):
    class Meta:
        model = models.ChildRegisteredAfter
        interfaces = (Node,)


class ParentWithRelationshipAsyncNode(AsyncMongoengineObjectType):
    class Meta:
        model = models.ParentWithRelationship
        interfaces = (Node,)


class ProfessorMetadataAsyncNode(AsyncMongoengineObjectType):
    class Meta:
        model = ProfessorMetadata
        interfaces = (graphene.Node,)


class ProfessorVectorAsyncNode(AsyncMongoengineObjectType):
    class Meta:
        model = models.ProfessorVector
        interfaces = (Node,)


class ErroneousModelAsyncNode(AsyncMongoengineObjectType):
    class Meta:
        model = models.ErroneousModel
        interfaces = (Node,)


class BarAsyncNode(AsyncMongoengineObjectType):
    class Meta:
        model = models.Bar
        interfaces = (Node,)


class FooAsyncNode(AsyncMongoengineObjectType):
    class Meta:
        model = models.Foo
        interfaces = (Node,)


# Deep select_related stress-test nodes
class DeepL10AsyncNode(AsyncMongoengineObjectType):
    class Meta:
        model = models.DeepL10
        interfaces = (Node,)


class DeepL9AsyncNode(AsyncMongoengineObjectType):
    class Meta:
        model = models.DeepL9
        interfaces = (Node,)


class DeepL8AsyncNode(AsyncMongoengineObjectType):
    class Meta:
        model = models.DeepL8
        interfaces = (Node,)


class DeepNestedEmbedAsyncType(AsyncMongoengineObjectType):
    """Async type for DeepNestedEmbed — registered before DeepEmbedWithRefAsyncType so the
    EmbeddedDocumentField converter for 'nested' can resolve the inner type at class-creation time."""

    class Meta:
        model = models.DeepNestedEmbed


class DeepEmbedWithRefAsyncType(AsyncMongoengineObjectType):
    """Async type for DeepEmbedWithRef — registered before DeepL7AsyncNode so the
    EmbeddedDocumentListField converter can resolve the inner type at class-creation time."""

    class Meta:
        model = models.DeepEmbedWithRef


class DeepL7AsyncNode(AsyncMongoengineObjectType):
    class Meta:
        model = models.DeepL7
        interfaces = (Node,)


class DeepL6AsyncNode(AsyncMongoengineObjectType):
    class Meta:
        model = models.DeepL6
        interfaces = (Node,)


class DeepL5AsyncNode(AsyncMongoengineObjectType):
    class Meta:
        model = models.DeepL5
        interfaces = (Node,)


class DeepL4AsyncNode(AsyncMongoengineObjectType):
    class Meta:
        model = models.DeepL4
        interfaces = (Node,)


class DeepL3AsyncNode(AsyncMongoengineObjectType):
    class Meta:
        model = models.DeepL3
        interfaces = (Node,)


class DeepL2AsyncNode(AsyncMongoengineObjectType):
    class Meta:
        model = models.DeepL2
        interfaces = (Node,)


class DeepL1AsyncNode(AsyncMongoengineObjectType):
    class Meta:
        model = models.DeepL1
        interfaces = (Node,)


class BenchAsyncNode(AsyncMongoengineObjectType):
    class Meta:
        model = models.Bench
        interfaces = (Node,)


class ExamAsyncNode(AsyncMongoengineObjectType):
    class Meta:
        model = models.Exam
        interfaces = (Node,)


class SchoolClassAsyncNode(AsyncMongoengineObjectType):
    class Meta:
        model = models.SchoolClass
        interfaces = (Node,)
        only_fields = ("allowed_grades", "subjects")


class EventAsyncNode(AsyncMongoengineObjectType):
    class Meta:
        model = models.Event
        interfaces = (Node,)
