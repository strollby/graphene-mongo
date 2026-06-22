from . import models
from graphene_mongo.synchronous.types import (
    MongoengineObjectType,
    MongoengineInterfaceType,
    MongoengineInputType,
)
from graphene.types.union import Union


class PublisherType(MongoengineObjectType):
    class Meta:
        model = models.Publisher


class EditorType(MongoengineObjectType):
    class Meta:
        model = models.Editor


class ArticleType(MongoengineObjectType):
    class Meta:
        model = models.Article


class EmbeddedArticleType(MongoengineObjectType):
    class Meta:
        model = models.EmbeddedArticle


class PlayerType(MongoengineObjectType):
    class Meta:
        model = models.Player


class ReporterType(MongoengineObjectType):
    class Meta:
        model = models.Reporter


class ParentType(MongoengineObjectType):
    class Meta:
        model = models.Parent


class ParentInterface(MongoengineInterfaceType):
    class Meta:
        model = models.Parent
        exclude_fields = ["loc"]


class ChildType(MongoengineObjectType):
    class Meta:
        model = models.Child
        interfaces = (ParentInterface,)


class AnotherChildType(MongoengineObjectType):
    class Meta:
        model = models.AnotherChild
        interfaces = (ParentInterface,)


class ChildUnionType(Union):
    class Meta:
        types = (ChildType, AnotherChildType)
        interfaces = (ParentInterface,)


class CellTowerType(MongoengineObjectType):
    class Meta:
        model = models.CellTower


class ProfessorMetadataType(MongoengineObjectType):
    class Meta:
        model = models.ProfessorMetadata


class ProfessorVectorType(MongoengineObjectType):
    class Meta:
        model = models.ProfessorVector


class ArticleInput(MongoengineInputType):
    class Meta:
        model = models.Article
        only_fields = ["headline"]


class EditorInput(MongoengineInputType):
    class Meta:
        model = models.Editor
        only_fields = ["first_name", "last_name"]
        # allow providing only one of those ! Even None...
        non_required_fields = ["first_name", "last_name"]


# ProfessorMetadataInput must be registered before ProfessorVectorInput so the
# EmbeddedDocumentField converter can resolve the nested type from the inputs registry.
class ProfessorMetadataInput(MongoengineInputType):
    class Meta:
        model = models.ProfessorMetadata
        only_fields = ["first_name", "last_name", "departments"]
        non_required_fields = ["first_name", "last_name", "departments"]


class ProfessorVectorInput(MongoengineInputType):
    class Meta:
        model = models.ProfessorVector
        only_fields = ["vec", "metadata"]
        non_required_fields = ["vec", "metadata"]


# Deep select_related stress-test types
class DeepL10Type(MongoengineObjectType):
    class Meta:
        model = models.DeepL10


class DeepL9Type(MongoengineObjectType):
    class Meta:
        model = models.DeepL9


class DeepL8Type(MongoengineObjectType):
    class Meta:
        model = models.DeepL8


class DeepL7Type(MongoengineObjectType):
    class Meta:
        model = models.DeepL7


class DeepL6Type(MongoengineObjectType):
    class Meta:
        model = models.DeepL6


class DeepL5Type(MongoengineObjectType):
    class Meta:
        model = models.DeepL5


class DeepL4Type(MongoengineObjectType):
    class Meta:
        model = models.DeepL4


class DeepL3Type(MongoengineObjectType):
    class Meta:
        model = models.DeepL3


class DeepL2Type(MongoengineObjectType):
    class Meta:
        model = models.DeepL2


class DeepL1Type(MongoengineObjectType):
    class Meta:
        model = models.DeepL1
