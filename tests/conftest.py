from collections.abc import AsyncGenerator
from datetime import datetime
import os
from typing import Any

import mongoengine
from mongomock import gridfs
import pytest

from .models import (
    AnotherChild,
    Article,
    Bench,
    CellTower,
    Child,
    ChildRegisteredAfter,
    ChildRegisteredBefore,
    DeepL1,
    DeepL2,
    DeepL3,
    DeepL4,
    DeepL5,
    DeepL6,
    DeepL7,
    DeepL8,
    DeepL9,
    DeepL10,
    DeepEmbedWithRef,
    DeepNestedEmbed,
    Editor,
    EmbeddedArticle,
    Event,
    Exam,
    GradeEnum,
    ParentWithRelationship,
    Player,
    ProfessorMetadata,
    ProfessorVector,
    Publisher,
    Reporter,
    School,
    SchoolClass,
)

current_dirname = os.path.dirname(os.path.abspath(__file__))
DB_NAME = "graphene-mongo-test" + (os.environ.get("TOX_ENV_NAME") or "").lower()


@pytest.fixture()
def fixtures_dirname():
    return os.path.join(current_dirname, "fixtures")


@pytest.fixture(scope="module")
def fixtures():
    Publisher.drop_collection()
    publisher1 = Publisher(name="Newsco")
    publisher1.save()

    Editor.drop_collection()
    editor1 = Editor(
        id="1",
        first_name="Penny",
        last_name="Hardaway",
        metadata={"age": "20", "nickname": "$1"},
        company=publisher1,
    )
    image_filename = os.path.join(current_dirname, "fixtures", "image.jpg")
    with open(image_filename, "rb") as f:
        editor1.avatar.put(f, content_type="image/jpeg")
    editor1.save()

    editor2 = Editor(id="2", first_name="Grant", last_name="Hill")
    editor2.save()
    editor3 = Editor(id="3", first_name="Dennis", last_name="Rodman")
    editor3.save()

    Article.drop_collection()
    pub_date = datetime.strptime("2020-01-01", "%Y-%m-%d")
    article1 = Article(headline="Hello", editor=editor1, pub_date=pub_date)
    article1.save()
    article2 = Article(headline="World", editor=editor2, pub_date=pub_date)
    article2.save()

    article3 = Article(headline="Bye", editor=editor2, pub_date=pub_date)
    article3.save()

    Reporter.drop_collection()
    reporter1 = Reporter(
        id="1",
        first_name="Allen",
        last_name="Iverson",
        email="ai@gmail.com",
        awards=["2010-mvp"],
        generic_references=[article1],
    )
    reporter1.articles = [article1, article2]
    embedded_article1 = EmbeddedArticle(headline="Real", editor=editor1)
    embedded_article2 = EmbeddedArticle(headline="World", editor=editor2)
    reporter1.embedded_articles = [embedded_article1, embedded_article2]
    reporter1.embedded_list_articles = [embedded_article2, embedded_article1]
    reporter1.generic_reference = article1
    reporter1.save()

    Player.drop_collection()
    player1 = Player(
        first_name="Michael",
        last_name="Jordan",
        articles=[article1, article2],
    )
    player1.save()
    player2 = Player(
        first_name="Magic",
        last_name="Johnson",
        opponent=player1,
        articles=[article3],
    )
    player2.save()
    player3 = Player(first_name="Larry", last_name="Bird", players=[player1, player2])
    player3.save()

    player1.players = [player2]
    player1.save()

    player2.players = [player1]
    player2.save()

    player4 = Player(first_name="Chris", last_name="Webber")
    player4.save()

    Child.drop_collection()
    child1 = Child(bar="BAR", baz="BAZ")
    child1.save()

    child2 = Child(bar="bar", baz="baz", loc=[10, 20])
    child2.save()

    another_child1 = AnotherChild(bar="BAR", qux="QUX")
    another_child1.save()

    another_child2 = AnotherChild(bar="bar", qux="qux", loc=[20, 10])
    another_child2.save()

    CellTower.drop_collection()
    ct = CellTower(
        code="bar",
        base=[
            [
                [-43.36556, -22.99669],
                [-43.36539, -23.01928],
                [-43.26583, -23.01802],
                [-43.36717, -22.98855],
                [-43.36636, -22.99351],
                [-43.36556, -22.99669],
            ]
        ],
        coverage_area=[
            [
                [
                    [-43.36556, -22.99669],
                    [-43.36539, -23.01928],
                    [-43.26583, -23.01802],
                    [-43.36717, -22.98855],
                    [-43.36636, -22.99351],
                    [-43.36556, -22.99669],
                ]
            ]
        ],
    )
    ct.save()
    ProfessorVector.drop_collection()
    professor_metadata = ProfessorMetadata(
        id="5e06aa20-6805-4eef-a144-5615dedbe32b",
        first_name="Steven",
        last_name="Curry",
        departments=["NBA", "MLB"],
    )
    professor_vector = ProfessorVector(vec=[1.0, 2.3], metadata=professor_metadata)
    professor_vector.save()

    ParentWithRelationship.drop_collection()
    ChildRegisteredAfter.drop_collection()
    ChildRegisteredBefore.drop_collection()

    # This is one messed up family

    # She'd better have presence this time
    child3 = ChildRegisteredBefore(name="Akari")
    child4 = ChildRegisteredAfter(name="Kyouko")
    child3.save()
    child4.save()

    parent = ParentWithRelationship(
        name="Yui",
        before_child=[child3],
        after_child=[child4],
    )

    parent.save()

    child3.parent = child4.parent = parent
    child3.save()
    child4.save()

    # Deep select_related chain — 10 levels
    for cls in [DeepL1, DeepL2, DeepL3, DeepL4, DeepL5, DeepL6, DeepL7, DeepL8, DeepL9, DeepL10]:
        cls.drop_collection()

    l10a = DeepL10(name="L10-A").save()
    l10b = DeepL10(name="L10-B").save()
    l10c = DeepL10(name="L10-C").save()

    l9 = DeepL9(name="L9", child=l10a).save()

    l8 = DeepL8(name="L8", child=l9, extras=[l10b, l10c], generic_refs=[l9, l10b]).save()

    l7 = DeepL7(
        name="L7",
        child=l8,
        embed=DeepEmbedWithRef(
            label="embed-single",
            ref_item=l10a,
            generic_item=l9,
            list_refs=[l10b, l10c],
            nested=DeepNestedEmbed(ref_item=l10a),
        ),
        embeds=[
            DeepEmbedWithRef(
                label="embed-list-0",
                ref_item=l10b,
                generic_item=l10c,
                list_refs=[l10a],
                nested=DeepNestedEmbed(ref_item=l10b),
            ),
            DeepEmbedWithRef(
                label="embed-list-1",
                ref_item=l10c,
                generic_item=l9,
                list_refs=[l10a, l10b],
                nested=DeepNestedEmbed(ref_item=l10c),
            ),
        ],
    ).save()

    l6 = DeepL6(name="L6", child=l7, generic_item=l7).save()

    l5a = DeepL5(name="L5-A", child=l6).save()
    l5b = DeepL5(name="L5-B", child=l6).save()
    l5a.siblings = [l5b]
    l5a.save()

    l4 = DeepL4(name="L4", child=l5a).save()

    l3 = DeepL3(name="L3", child=l4, generic_item=l4, extra_refs=[l5a, l5b]).save()

    l2a = DeepL2(name="L2-A", child=l3).save()
    l2b = DeepL2(name="L2-B", child=l3).save()

    DeepL1(name="L1", child=l2a, children=[l2a, l2b]).save()

    # Enum field models
    for cls in [Bench, Exam, SchoolClass, School]:
        cls.drop_collection()

    bench1 = Bench(size=10).save()
    bench2 = Bench(size=20).save()
    exam1 = Exam(size=5).save()

    sc1 = SchoolClass(
        allowed_grades=[GradeEnum.A, GradeEnum.B],
        subjects=["math", "science"],
        records=[bench1, exam1],
    ).save()
    sc2 = SchoolClass(
        allowed_grades=[GradeEnum.B],
        subjects=["history"],
        records=[bench2],
    ).save()

    School(classes=[sc1, sc2]).save()

    # AwareDateTimeField model
    Event.drop_collection()
    from zoneinfo import ZoneInfo
    import datetime as _dt

    Event(
        name="Kolkata Summit",
        start_time=_dt.datetime(2024, 6, 15, 14, 30, tzinfo=ZoneInfo("Asia/Kolkata")),
    ).save()
    Event(
        name="New York Meetup",
        start_time=_dt.datetime(2024, 9, 1, 9, 0, tzinfo=ZoneInfo("America/New_York")),
    ).save()

    return True


@pytest.fixture(scope="session", autouse=True)
async def setup() -> AsyncGenerator[None, Any]:
    """
    Handles the database connection lifecycle for the entire session.
    """
    gridfs.enable_gridfs_integration()

    host = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")
    mongoengine.connect(DB_NAME, host=host)
    mongoengine.async_connect(DB_NAME, host=host)
