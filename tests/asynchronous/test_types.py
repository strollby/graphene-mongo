from graphene import Field, Int, Interface, ObjectType
from graphene.relay import Node, is_node
from pytest import raises

from ..models import (
    Article,
    Bench,
    Child,
    EmbeddedArticle,
    Exam,
    Parent,
    Reporter,
    School,
    SchoolClass,
    Student,
)
from .utils import with_local_async_registry
from graphene_mongo.asynchronous.types import AsyncMongoengineObjectType, AsyncMongoengineObjectTypeOptions
from graphene_mongo.base.registry import Registry
from graphene_mongo.base.utils import ExecutorEnum

# Use a private registry so module-level class definitions don't disturb the
# global async registry (which holds the relay nodes used by other test modules).
_types_registry = Registry(executor=ExecutorEnum.ASYNC)


class HumanAsync(AsyncMongoengineObjectType):
    pub_date = Int()

    class Meta:
        model = Article
        registry = _types_registry
        interfaces = (Node,)


class BeingAsync(AsyncMongoengineObjectType):
    class Meta:
        model = EmbeddedArticle
        registry = _types_registry
        interfaces = (Node,)


class CharacterAsync(AsyncMongoengineObjectType):
    class Meta:
        model = Reporter
        registry = _types_registry


class DadAsync(AsyncMongoengineObjectType):
    class Meta:
        model = Parent
        registry = _types_registry


class SonAsync(AsyncMongoengineObjectType):
    class Meta:
        model = Child
        registry = _types_registry


def test_mongoengine_interface():
    assert issubclass(Node, Interface)
    assert issubclass(Node, Node)


def test_objecttype_registered():
    assert issubclass(CharacterAsync, ObjectType)
    assert CharacterAsync._meta.model == Reporter
    assert set(CharacterAsync._meta.fields.keys()) == set(
        [
            "id",
            "first_name",
            "last_name",
            "email",
            "embedded_articles",
            "embedded_list_articles",
            "articles",
            "awards",
            "generic_reference",
            "generic_embedded_document",
            "generic_references",
        ]
    )


def test_mongoengine_inheritance():
    assert issubclass(SonAsync._meta.model, DadAsync._meta.model)


def test_node_replacedfield():
    idfield = HumanAsync._meta.fields["pub_date"]
    assert isinstance(idfield, Field)
    assert idfield.type == Int


def test_object_type():
    assert issubclass(HumanAsync, ObjectType)
    assert set(HumanAsync._meta.fields.keys()) == set(
        [
            "id",
            "headline",
            "pub_date",
            "editor",
            "reporter",
        ]
    )
    assert is_node(HumanAsync)


def test_should_raise_if_no_model():
    with raises(Exception) as excinfo:
        class Human1(AsyncMongoengineObjectType):
            pass

    assert "valid Mongoengine Model" in str(excinfo.value)


def test_should_raise_if_model_is_invalid():
    with raises(Exception) as excinfo:
        class Human2(AsyncMongoengineObjectType):
            class Meta:
                model = 1

    assert "valid Mongoengine Model" in str(excinfo.value)


@with_local_async_registry
def test_mongoengine_objecttype_only_fields():
    class A(AsyncMongoengineObjectType):
        class Meta:
            model = Article
            only_fields = "headline"

    fields = set(A._meta.fields.keys())
    assert fields == set(["headline"])


@with_local_async_registry
def test_mongoengine_objecttype_exclude_fields():
    class A(AsyncMongoengineObjectType):
        class Meta:
            model = Article
            exclude_fields = "headline"

    assert "headline" not in list(A._meta.fields.keys())


@with_local_async_registry
def test_mongoengine_objecttype_order_by():
    class A(AsyncMongoengineObjectType):
        class Meta:
            model = Article
            order_by = "some_order_by_statement"

    assert "some_order_by_statement" not in list(A._meta.fields.keys())


@with_local_async_registry
def test_passing_meta_when_subclassing_mongoengine_objecttype():
    class TypeSubclassWithBadOptions(AsyncMongoengineObjectType):
        class Meta:
            abstract = True

        @classmethod
        def __init_subclass_with_meta__(cls, **kwargs):
            _meta = ["hi"]
            super(TypeSubclassWithBadOptions, cls).__init_subclass_with_meta__(
                _meta=_meta, **kwargs
            )

    with raises(Exception) as einfo:
        class A(TypeSubclassWithBadOptions):
            class Meta:
                model = Article

    assert "MongoengineGenericObjectTypeOptions" in str(einfo.value)

    class TypeSubclass(AsyncMongoengineObjectType):
        class Meta:
            abstract = True

        @classmethod
        def __init_subclass_with_meta__(cls, some_subclass_attr=None, **kwargs):
            _meta = AsyncMongoengineObjectTypeOptions(cls)
            _meta.some_subclass_attr = some_subclass_attr
            super(TypeSubclass, cls).__init_subclass_with_meta__(_meta=_meta, **kwargs)

    class B(TypeSubclass):
        class Meta:
            model = Article
            some_subclass_attr = "someval"

    assert hasattr(B._meta, "some_subclass_attr")
    assert B._meta.some_subclass_attr == "someval"


@with_local_async_registry
def test_filter_list_types():
    """
    Test to check filter args should not be generated for the following types of fields:

    ListField(EmbeddedDocumentListField(...))
    ListField(GenericEmbeddedDocumentField(...))
    """

    class ExamType(AsyncMongoengineObjectType):
        class Meta:
            model = Exam

    class BenchType(AsyncMongoengineObjectType):
        class Meta:
            model = Bench

    class StudentType(AsyncMongoengineObjectType):
        class Meta:
            model = Student

    class SchoolClassType(AsyncMongoengineObjectType):
        class Meta:
            model = SchoolClass
            interfaces = (Node,)

    class SchoolType(AsyncMongoengineObjectType):
        class Meta:
            model = School
            interfaces = (Node,)

    class_type_filter_args = SchoolType._meta.fields["classes"].args
    assert class_type_filter_args.keys() == {
        "before",
        "after",
        "first",
        "last",
        "allowed_grades",
        "id",
        "subjects",
    }
