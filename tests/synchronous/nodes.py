import graphene
from graphene.relay import Node

from .. import models
from .. import types  # noqa: F401
from ..models import ProfessorMetadata
from graphene_mongo.synchronous.types import MongoengineObjectType


class PublisherNode(MongoengineObjectType):
    legal_name = graphene.String()
    bad_field = graphene.String()

    class Meta:
        model = models.Publisher
        only_fields = ("id", "name")
        interfaces = (Node,)


class ArticleNode(MongoengineObjectType):
    class Meta:
        model = models.Article
        interfaces = (Node,)


class EditorNode(MongoengineObjectType):
    class Meta:
        model = models.Editor
        interfaces = (Node,)


class EmbeddedArticleNode(MongoengineObjectType):
    class Meta:
        model = models.EmbeddedArticle
        interfaces = (Node,)


class PlayerNode(MongoengineObjectType):
    class Meta:
        model = models.Player
        interfaces = (Node,)
        filter_fields = {"first_name": ["istartswith", "in"]}


class ReporterNode(MongoengineObjectType):
    class Meta:
        model = models.Reporter
        interfaces = (Node,)


class ParentNode(MongoengineObjectType):
    class Meta:
        model = models.Parent
        interfaces = (Node,)


class ChildNode(MongoengineObjectType):
    class Meta:
        model = models.Child
        interfaces = (Node,)


class ChildRegisteredBeforeNode(MongoengineObjectType):
    class Meta:
        model = models.ChildRegisteredBefore
        interfaces = (Node,)


class ChildRegisteredAfterNode(MongoengineObjectType):
    class Meta:
        model = models.ChildRegisteredAfter
        interfaces = (Node,)


class ParentWithRelationshipNode(MongoengineObjectType):
    class Meta:
        model = models.ParentWithRelationship
        interfaces = (Node,)


class ProfessorMetadataNode(MongoengineObjectType):
    class Meta:
        model = ProfessorMetadata
        interfaces = (graphene.Node,)


class ProfessorVectorNode(MongoengineObjectType):
    class Meta:
        model = models.ProfessorVector
        interfaces = (Node,)


class ErroneousModelNode(MongoengineObjectType):
    class Meta:
        model = models.ErroneousModel
        interfaces = (Node,)


class BarNode(MongoengineObjectType):
    class Meta:
        model = models.Bar
        interfaces = (Node,)


class FooNode(MongoengineObjectType):
    class Meta:
        model = models.Foo
        interfaces = (Node,)


# Deep select_related stress-test nodes
class DeepL10Node(MongoengineObjectType):
    class Meta:
        model = models.DeepL10
        interfaces = (Node,)


class DeepL9Node(MongoengineObjectType):
    class Meta:
        model = models.DeepL9
        interfaces = (Node,)


class DeepL8Node(MongoengineObjectType):
    class Meta:
        model = models.DeepL8
        interfaces = (Node,)


class DeepNestedEmbedType(MongoengineObjectType):
    """Sync type for DeepNestedEmbed — registered before DeepEmbedWithRefType so the
    EmbeddedDocumentField converter for 'nested' can resolve the inner type at class-creation time."""

    class Meta:
        model = models.DeepNestedEmbed


class DeepEmbedWithRefType(MongoengineObjectType):
    """Sync type for DeepEmbedWithRef — registered before DeepL7Node so the
    EmbeddedDocumentListField converter can resolve the inner type at class-creation time."""

    class Meta:
        model = models.DeepEmbedWithRef


class DeepL7Node(MongoengineObjectType):
    class Meta:
        model = models.DeepL7
        interfaces = (Node,)


class DeepL6Node(MongoengineObjectType):
    class Meta:
        model = models.DeepL6
        interfaces = (Node,)


class DeepL5Node(MongoengineObjectType):
    class Meta:
        model = models.DeepL5
        interfaces = (Node,)


class DeepL4Node(MongoengineObjectType):
    class Meta:
        model = models.DeepL4
        interfaces = (Node,)


class DeepL3Node(MongoengineObjectType):
    class Meta:
        model = models.DeepL3
        interfaces = (Node,)


class DeepL2Node(MongoengineObjectType):
    class Meta:
        model = models.DeepL2
        interfaces = (Node,)


class DeepL1Node(MongoengineObjectType):
    class Meta:
        model = models.DeepL1
        interfaces = (Node,)


class BenchNode(MongoengineObjectType):
    class Meta:
        model = models.Bench
        interfaces = (Node,)


class ExamNode(MongoengineObjectType):
    class Meta:
        model = models.Exam
        interfaces = (Node,)


class SchoolClassNode(MongoengineObjectType):
    class Meta:
        model = models.SchoolClass
        interfaces = (Node,)
        only_fields = ("allowed_grades", "subjects")


class EventNode(MongoengineObjectType):
    class Meta:
        model = models.Event
        interfaces = (Node,)
