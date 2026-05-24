import graphene

from graphene_mongo import registry
from graphene_mongo.base.converter import convert_mongoengine_field
from graphene_mongo.asynchronous.fields import AsyncMongoengineConnectionField
from graphene_mongo.asynchronous.types import AsyncMongoengineObjectType

from ..models import (
    Article,
    Editor,
    EmbeddedArticle,
    EmbeddedFoo,
    Player,
    ProfessorMetadata,
    ProfessorVector,
    Publisher,
    Reporter,
)


def test_should_reference_convert_dynamic():
    class E(AsyncMongoengineObjectType):
        class Meta:
            model = Editor
            interfaces = (graphene.Node,)

    dynamic_field = convert_mongoengine_field(EmbeddedArticle._fields["editor"], E._meta.registry)
    assert isinstance(dynamic_field, graphene.Dynamic)
    graphene_type = dynamic_field.get_type()
    assert isinstance(graphene_type, graphene.Field)
    assert graphene_type.type == E


def test_should_lazy_reference_convert_dynamic():
    class P(AsyncMongoengineObjectType):
        class Meta:
            model = Publisher
            interfaces = (graphene.Node,)

    dynamic_field = convert_mongoengine_field(Editor._fields["company"], P._meta.registry)
    assert isinstance(dynamic_field, graphene.Dynamic)
    graphene_type = dynamic_field.get_type()
    assert isinstance(graphene_type, graphene.Field)
    assert graphene_type.type == P


def test_should_embedded_convert_dynamic():
    class PM(AsyncMongoengineObjectType):
        class Meta:
            model = ProfessorMetadata
            interfaces = (graphene.Node,)

    dynamic_field = convert_mongoengine_field(
        ProfessorVector._fields["metadata"], PM._meta.registry
    )
    assert isinstance(dynamic_field, graphene.Dynamic)
    graphene_type = dynamic_field.get_type()
    assert isinstance(graphene_type, graphene.Field)
    assert graphene_type.type == PM


def test_should_convert_none():
    registry.reset_global_async_registry()
    dynamic_field = convert_mongoengine_field(
        EmbeddedArticle._fields["editor"], registry.get_global_async_registry()
    )
    assert isinstance(dynamic_field, graphene.Dynamic)
    graphene_type = dynamic_field.get_type()
    assert graphene_type is None


def test_should_convert_none_lazily():
    registry.reset_global_async_registry()
    dynamic_field = convert_mongoengine_field(
        Editor._fields["company"], registry.get_global_async_registry()
    )
    assert isinstance(dynamic_field, graphene.Dynamic)
    graphene_type = dynamic_field.get_type()
    assert graphene_type is None


def test_should_list_of_reference_convert_list():
    class A(AsyncMongoengineObjectType):
        class Meta:
            model = Article

    graphene_field = convert_mongoengine_field(Reporter._fields["articles"], A._meta.registry)
    assert isinstance(graphene_field, graphene.List)
    dynamic_field = graphene_field.get_type()
    assert dynamic_field._of_type == A


def test_should_list_of_generic_reference_covert_list():
    class A(AsyncMongoengineObjectType):
        class Meta:
            model = Article

    class E(AsyncMongoengineObjectType):
        class Meta:
            model = Editor

    class R(AsyncMongoengineObjectType):
        class Meta:
            model = Reporter

    generic_references_field = convert_mongoengine_field(
        Reporter._fields["generic_references"], registry.get_global_async_registry()
    )
    assert isinstance(generic_references_field, graphene.List)
    field = generic_references_field.get_type()
    assert field._of_type._meta.types == (A, E)


def test_should_list_of_embedded_convert_list():
    class E(AsyncMongoengineObjectType):
        class Meta:
            model = EmbeddedArticle

    graphene_field = convert_mongoengine_field(
        Reporter._fields["embedded_articles"], E._meta.registry
    )
    assert isinstance(graphene_field, graphene.List)
    dynamic_field = graphene_field.get_type()
    assert dynamic_field._of_type == E


def test_should_embedded_list_convert_list():
    class E(AsyncMongoengineObjectType):
        class Meta:
            model = EmbeddedArticle

    graphene_field = convert_mongoengine_field(
        Reporter._fields["embedded_list_articles"], E._meta.registry
    )
    assert isinstance(graphene_field, graphene.List)
    dynamic_field = graphene_field.get_type()
    assert dynamic_field._of_type == E


def test_should_self_reference_convert_dynamic():
    class P(AsyncMongoengineObjectType):
        class Meta:
            model = Player
            interfaces = (graphene.Node,)

    dynamic_field = convert_mongoengine_field(Player._fields["opponent"], P._meta.registry)
    assert isinstance(dynamic_field, graphene.Dynamic)
    graphene_type = dynamic_field.get_type()
    assert isinstance(graphene_type, graphene.Field)
    assert graphene_type.type == P

    graphene_field = convert_mongoengine_field(Player._fields["players"], P._meta.registry)
    assert isinstance(graphene_field, AsyncMongoengineConnectionField)


def test_should_list_of_self_reference_convert_list():
    class A(AsyncMongoengineObjectType):
        class Meta:
            model = Article

    class P(AsyncMongoengineObjectType):
        class Meta:
            model = Player

    graphene_field = convert_mongoengine_field(Player._fields["players"], P._meta.registry)
    assert isinstance(graphene_field, graphene.List)
    dynamic_field = graphene_field.get_type()
    assert dynamic_field._of_type == P


def test_should_description_convert_common_metadata():
    class A(AsyncMongoengineObjectType):
        class Meta:
            model = Article

    headline_field = convert_mongoengine_field(Article._fields["headline"], A._meta.registry)
    assert headline_field.kwargs["description"] == "The article headline."

    pubDate_field = convert_mongoengine_field(Article._fields["pub_date"], A._meta.registry)
    assert pubDate_field.kwargs["description"] == "Publication Date\nThe date of first press."

    firstName_field = convert_mongoengine_field(Editor._fields["first_name"], A._meta.registry)
    assert firstName_field.kwargs["description"] == "Editor's first name.\n(fname)"

    metadata_field = convert_mongoengine_field(Editor._fields["metadata"], A._meta.registry)
    assert metadata_field.kwargs["description"] == "Arbitrary metadata."


def test_should_description_convert_reference_metadata():
    class A(AsyncMongoengineObjectType):
        class Meta:
            model = Article

    class E(AsyncMongoengineObjectType):
        class Meta:
            model = Editor

    editor_field = convert_mongoengine_field(Article._fields["editor"], A._meta.registry).get_type()
    assert editor_field.description == "An Editor of a publication."


def test_should_generic_reference_convert_union():
    class A(AsyncMongoengineObjectType):
        class Meta:
            model = Article

    class E(AsyncMongoengineObjectType):
        class Meta:
            model = Editor

    class R(AsyncMongoengineObjectType):
        class Meta:
            model = Reporter

    generic_reference_field = convert_mongoengine_field(
        Reporter._fields["generic_reference"], registry.get_global_async_registry()
    )
    assert isinstance(generic_reference_field, graphene.Field)
    if not Reporter._fields["generic_reference"].required:
        assert isinstance(generic_reference_field.type(), graphene.Union)
        assert generic_reference_field.type()._meta.types == (A, E)
    else:
        assert issubclass(generic_reference_field.type.of_type, graphene.Union)
        assert generic_reference_field.type.of_type._meta.types == (A, E)


def test_should_generic_embedded_document_convert_union():
    class D(AsyncMongoengineObjectType):
        class Meta:
            model = EmbeddedArticle

    class F(AsyncMongoengineObjectType):
        class Meta:
            model = EmbeddedFoo

    class A(AsyncMongoengineObjectType):
        class Meta:
            model = Article

    class E(AsyncMongoengineObjectType):
        class Meta:
            model = Editor

    class R(AsyncMongoengineObjectType):
        class Meta:
            model = Reporter

    generic_embedded_document = convert_mongoengine_field(
        Reporter._fields["generic_embedded_document"], registry.get_global_async_registry()
    )
    assert isinstance(generic_embedded_document, graphene.Field)
    assert isinstance(generic_embedded_document.type(), graphene.Union)
    assert generic_embedded_document.type()._meta.types == (D, F)
