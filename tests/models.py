from datetime import datetime
from enum import Enum

import mongoengine


class Publisher(mongoengine.Document):
    meta = {"collection": "test_publisher"}
    name = mongoengine.StringField()

    @property
    def legal_name(self):
        return self.name + " Inc."

    def bad_field(self):
        return None


class Editor(mongoengine.Document):
    """
    An Editor of a publication.
    """

    meta = {"collection": "test_editor"}
    id = mongoengine.StringField(primary_key=True)
    first_name = mongoengine.StringField(
        required=True, help_text="Editor's first name.", db_field="fname"
    )
    last_name = mongoengine.StringField(required=True, help_text="Editor's last name.")
    metadata = mongoengine.MapField(
        field=mongoengine.StringField(), help_text="Arbitrary metadata."
    )
    company = mongoengine.ReferenceField(Publisher)
    avatar = mongoengine.FileField()
    seq = mongoengine.SequenceField()


class Article(mongoengine.Document):
    meta = {"collection": "test_article"}
    headline = mongoengine.StringField(required=True, help_text="The article headline.")
    pub_date = mongoengine.DateTimeField(
        default=datetime.now,
        verbose_name="publication date",
        help_text="The date of first press.",
    )
    editor = mongoengine.ReferenceField(Editor)
    reporter = mongoengine.ReferenceField("Reporter")
    # Will not convert these fields cause no choices
    # generic_reference = mongoengine.GenericReferenceField()
    # generic_embedded_document = mongoengine.GenericEmbeddedDocumentField()


class EmbeddedArticle(mongoengine.EmbeddedDocument):
    meta = {"collection": "test_embedded_article"}
    headline = mongoengine.StringField(required=True)
    pub_date = mongoengine.DateTimeField(default=datetime.now)
    editor = mongoengine.ReferenceField(Editor)
    reporter = mongoengine.ReferenceField("Reporter")


class EmbeddedFoo(mongoengine.EmbeddedDocument):
    meta = {"collection": "test_embedded_foo"}
    bar = mongoengine.StringField()


class Reporter(mongoengine.Document):
    meta = {"collection": "test_reporter"}
    id = mongoengine.StringField(primary_key=True)
    first_name = mongoengine.StringField(required=True)
    last_name = mongoengine.StringField(required=True)
    email = mongoengine.EmailField()
    awards = mongoengine.ListField(mongoengine.StringField())
    articles = mongoengine.ListField(mongoengine.ReferenceField(Article))
    embedded_articles = mongoengine.ListField(
        mongoengine.EmbeddedDocumentField(EmbeddedArticle),
    )
    embedded_list_articles = mongoengine.EmbeddedDocumentListField(EmbeddedArticle)
    generic_reference = mongoengine.GenericReferenceField(choices=[Article, Editor], required=True)
    generic_embedded_document = mongoengine.GenericEmbeddedDocumentField(
        choices=[EmbeddedArticle, EmbeddedFoo]
    )
    generic_references = mongoengine.ListField(
        mongoengine.GenericReferenceField(choices=[Article, Editor])
    )


class Player(mongoengine.Document):
    meta = {"collection": "test_player"}
    first_name = mongoengine.StringField(required=True)
    last_name = mongoengine.StringField(required=True)
    opponent = mongoengine.ReferenceField("Player")
    players = mongoengine.ListField(mongoengine.ReferenceField("Player"))
    articles = mongoengine.ListField(mongoengine.ReferenceField("Article"))
    embedded_list_articles = mongoengine.EmbeddedDocumentListField(EmbeddedArticle)


class Parent(mongoengine.Document):
    meta = {"collection": "test_parent", "allow_inheritance": True}
    bar = mongoengine.StringField()
    loc = mongoengine.MultiPolygonField()


class CellTower(mongoengine.Document):
    meta = {"collection": "test_cell_tower"}
    code = mongoengine.StringField()
    base = mongoengine.PolygonField()
    coverage_area = mongoengine.MultiPolygonField()


class Child(Parent):
    baz = mongoengine.StringField()
    loc = mongoengine.PointField()


class AnotherChild(Parent):
    qux = mongoengine.StringField()
    loc = mongoengine.PointField()


class ProfessorMetadata(mongoengine.EmbeddedDocument):
    meta = {"collection": "test_professor_metadata"}
    id = mongoengine.StringField(primary_key=False)
    first_name = mongoengine.StringField()
    last_name = mongoengine.StringField()
    departments = mongoengine.ListField(mongoengine.StringField())


class ProfessorVector(mongoengine.Document):
    meta = {"collection": "test_professor_vector"}
    vec = mongoengine.ListField(mongoengine.FloatField())
    metadata = mongoengine.EmbeddedDocumentField(ProfessorMetadata)


class ParentWithRelationship(mongoengine.Document):
    meta = {"collection": "test_parent_reference"}
    before_child = mongoengine.ListField(
        mongoengine.ReferenceField("ChildRegisteredBefore"),
    )
    after_child = mongoengine.ListField(
        mongoengine.ReferenceField("ChildRegisteredAfter"),
    )
    name = mongoengine.StringField()


class ChildRegisteredBefore(mongoengine.Document):
    meta = {"collection": "test_child_before_reference"}
    parent = mongoengine.ReferenceField(ParentWithRelationship)
    name = mongoengine.StringField()


class ChildRegisteredAfter(mongoengine.Document):
    meta = {"collection": "test_child_after_reference"}
    parent = mongoengine.ReferenceField(ParentWithRelationship)
    name = mongoengine.StringField()


class ErroneousModel(mongoengine.Document):
    meta = {"collection": "test_colliding_objects_model"}

    objects = mongoengine.ListField(mongoengine.StringField())


class Bar(mongoengine.EmbeddedDocument):
    some_list_field = mongoengine.ListField(mongoengine.StringField(), required=True)


class Foo(mongoengine.Document):
    bars = mongoengine.EmbeddedDocumentListField(Bar)


class GradeEnum(Enum):
    A = "A"
    B = "B"


class Student(mongoengine.EmbeddedDocument):
    name = mongoengine.StringField()


class Teacher(mongoengine.EmbeddedDocument):
    name = mongoengine.StringField()


class Bench(mongoengine.Document):
    size = mongoengine.IntField()


class Exam(mongoengine.Document):
    size = mongoengine.IntField()


class SchoolClass(mongoengine.Document):
    allowed_grades = mongoengine.ListField(mongoengine.EnumField(GradeEnum))
    subjects = mongoengine.ListField(mongoengine.StringField())
    students = mongoengine.ListField(mongoengine.EmbeddedDocumentListField(Student))
    members = mongoengine.ListField(
        mongoengine.GenericEmbeddedDocumentField(choices=[Student, Teacher])
    )
    records = mongoengine.ListField(mongoengine.GenericReferenceField(choices=[Bench, Exam]))


class School(mongoengine.Document):
    classes = mongoengine.ListField(mongoengine.ReferenceField(SchoolClass))


# ---------------------------------------------------------------------------
# Deep select_related stress-test models — 10-level reference chain
# ---------------------------------------------------------------------------


class DeepL10(mongoengine.Document):
    meta = {"collection": "test_deep_l10"}
    name = mongoengine.StringField()


class DeepL9(mongoengine.Document):
    meta = {"collection": "test_deep_l9"}
    name = mongoengine.StringField()
    child = mongoengine.ReferenceField(DeepL10)


class DeepL8(mongoengine.Document):
    meta = {"collection": "test_deep_l8"}
    name = mongoengine.StringField()
    child = mongoengine.ReferenceField(DeepL9)
    # list of references at level 8 → level 10
    extras = mongoengine.ListField(mongoengine.ReferenceField(DeepL10))
    # list of generic references — scenario 1
    generic_refs = mongoengine.ListField(
        mongoengine.GenericReferenceField(choices=[DeepL9, DeepL10])
    )


class DeepNestedEmbed(mongoengine.EmbeddedDocument):
    """Nested EmbeddedDocument — lives inside DeepEmbedWithRef to test recursive embedded-doc path generation."""

    ref_item = mongoengine.ReferenceField(DeepL10)


class DeepEmbedWithRef(mongoengine.EmbeddedDocument):
    """EmbeddedDocument with ReferenceField, GenericReferenceField, ListField(ReferenceField),
    and a nested EmbeddedDocumentField for deep select_related tests."""

    label = mongoengine.StringField()
    ref_item = mongoengine.ReferenceField(DeepL10)
    generic_item = mongoengine.GenericReferenceField(choices=[DeepL9, DeepL10])
    # list of references inside an embedded doc — scenario 2
    list_refs = mongoengine.ListField(mongoengine.ReferenceField(DeepL10))
    # nested embedded doc with a reference — scenario 3
    nested = mongoengine.EmbeddedDocumentField(DeepNestedEmbed)


class DeepL7(mongoengine.Document):
    meta = {"collection": "test_deep_l7"}
    name = mongoengine.StringField()
    child = mongoengine.ReferenceField(DeepL8)
    # single embedded doc with ref fields
    embed = mongoengine.EmbeddedDocumentField(DeepEmbedWithRef)
    # list of embedded docs with ref fields
    embeds = mongoengine.EmbeddedDocumentListField(DeepEmbedWithRef)


class DeepL6(mongoengine.Document):
    meta = {"collection": "test_deep_l6"}
    name = mongoengine.StringField()
    child = mongoengine.ReferenceField(DeepL7)
    # generic reference at level 6 — can point at L7 or L8
    generic_item = mongoengine.GenericReferenceField(choices=[DeepL7, DeepL8])


class DeepL5(mongoengine.Document):
    meta = {"collection": "test_deep_l5"}
    name = mongoengine.StringField()
    child = mongoengine.ReferenceField(DeepL6)
    # list of sibling-level references
    siblings = mongoengine.ListField(mongoengine.ReferenceField("DeepL5"))


class DeepL4(mongoengine.Document):
    meta = {"collection": "test_deep_l4"}
    name = mongoengine.StringField()
    child = mongoengine.ReferenceField(DeepL5)


class DeepL3(mongoengine.Document):
    meta = {"collection": "test_deep_l3"}
    name = mongoengine.StringField()
    child = mongoengine.ReferenceField(DeepL4)
    # generic reference at level 3 — can point at L4 or L5
    generic_item = mongoengine.GenericReferenceField(choices=[DeepL4, DeepL5])
    # list of references to a deeper level
    extra_refs = mongoengine.ListField(mongoengine.ReferenceField(DeepL5))


class DeepL2(mongoengine.Document):
    meta = {"collection": "test_deep_l2"}
    name = mongoengine.StringField()
    child = mongoengine.ReferenceField(DeepL3)


class DeepL1(mongoengine.Document):
    meta = {"collection": "test_deep_l1"}
    name = mongoengine.StringField()
    child = mongoengine.ReferenceField(DeepL2)
    # list of references at level 1 → level 2
    children = mongoengine.ListField(mongoengine.ReferenceField(DeepL2))


class Event(mongoengine.Document):
    """Test model for AwareDateTimeField — stores a name and a timezone-aware start time."""

    meta = {"collection": "test_event"}
    name = mongoengine.StringField(required=True)
    start_time = mongoengine.AwareDateTimeField()
