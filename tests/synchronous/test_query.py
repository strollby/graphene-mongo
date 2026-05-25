import base64
import json
import os

import graphene

from .. import models
from .. import types
from .utils import execute_count


def test_should_query_editor(fixtures, fixtures_dirname):
    class Query(graphene.ObjectType):
        editor = graphene.Field(types.EditorType)
        editors = graphene.List(types.EditorType)

        def resolve_editor(self, *args, **kwargs):
            return models.Editor.objects.select_related("company").first()

        def resolve_editors(self, *args, **kwargs):
            return list(models.Editor.objects.all())

    query = """
        query EditorQuery {
            editor {
                firstName,
                metadata,
                company {
                    name
                },
                avatar {
                    contentType,
                    chunkSize,
                    length,
                    data
                }
            }
            editors {
                firstName,
                lastName
            }
        }
    """

    avator_filename = os.path.join(fixtures_dirname, "image.jpg")
    with open(avator_filename, "rb") as f:
        data = base64.b64encode(f.read())

    expected = {
        "editor": {
            "firstName": "Penny",
            "company": {"name": "Newsco"},
            "avatar": {
                "contentType": "image/jpeg",
                "chunkSize": 261120,
                "length": 46928,
                "data": data.decode("utf-8"),
            },
        },
        "editors": [
            {"firstName": "Penny", "lastName": "Hardaway"},
            {"firstName": "Grant", "lastName": "Hill"},
            {"firstName": "Dennis", "lastName": "Rodman"},
        ],
    }
    expected_metadata = {"age": "20", "nickname": "$1"}

    schema = graphene.Schema(query=Query)
    result, count = execute_count(schema, query)
    assert not result.errors
    metadata = result.data["editor"].pop("metadata")
    assert json.loads(metadata) == expected_metadata
    assert result.data == expected
    assert count == 4  # 1 first editor (company pre-fetched via select_related) + 2 GridFS reads (files+chunks) + 1 all editors


def test_should_query_reporter(fixtures):
    class Query(graphene.ObjectType):
        reporter = graphene.Field(types.ReporterType)

        def resolve_reporter(self, *args, **kwargs):
            return models.Reporter.objects.select_related("articles").first()

    query = """
        query ReporterQuery {
            reporter {
                firstName,
                lastName,
                email,
                articles {
                    headline
                },
                embeddedArticles {
                    headline
                },
                embeddedListArticles {
                    headline
                },
                awards
            }
        }
    """
    expected = {
        "reporter": {
            "firstName": "Allen",
            "lastName": "Iverson",
            "email": "ai@gmail.com",
            "articles": [{"headline": "Hello"}, {"headline": "World"}],
            "embeddedArticles": [{"headline": "Real"}, {"headline": "World"}],
            "embeddedListArticles": [{"headline": "World"}, {"headline": "Real"}],
            "awards": ["2010-mvp"],
        }
    }

    schema = graphene.Schema(query=Query)
    result, count = execute_count(schema, query)
    assert not result.errors
    assert result.data == expected
    assert count == 1


def test_should_custom_kwargs(fixtures):
    class Query(graphene.ObjectType):
        editors = graphene.List(types.EditorType, first=graphene.Int())

        def resolve_editors(self, *args, **kwargs):
            editors = models.Editor.objects()
            if "first" in kwargs:
                editors = editors[: kwargs["first"]]
            return list(editors)

    query = """
        query EditorQuery {
            editors(first: 2) {
                firstName,
                lastName
            }
        }
    """
    expected = {
        "editors": [
            {"firstName": "Penny", "lastName": "Hardaway"},
            {"firstName": "Grant", "lastName": "Hill"},
        ]
    }
    schema = graphene.Schema(query=Query)
    result, count = execute_count(schema, query)
    assert not result.errors
    assert result.data == expected
    assert count == 1


def test_should_self_reference(fixtures):
    class Query(graphene.ObjectType):
        all_players = graphene.List(types.PlayerType)

        def resolve_all_players(self, *args, **kwargs):
            return models.Player.objects.select_related("players", "opponent").all()

    query = """
        query PlayersQuery {
            allPlayers {
                firstName,
                opponent {
                    firstName
                },
                players {
                    firstName
                }
            }
        }
    """
    expected = {
        "allPlayers": [
            {
                "firstName": "Michael",
                "opponent": None,
                "players": [{"firstName": "Magic"}],
            },
            {
                "firstName": "Magic",
                "opponent": {"firstName": "Michael"},
                "players": [{"firstName": "Michael"}],
            },
            {
                "firstName": "Larry",
                "opponent": None,
                "players": [{"firstName": "Michael"}, {"firstName": "Magic"}],
            },
            {"firstName": "Chris", "opponent": None, "players": []},
        ]
    }
    schema = graphene.Schema(query=Query)
    result, count = execute_count(schema, query)
    assert not result.errors
    assert result.data == expected
    assert count == 1  # 1 select_related aggregate (opponent + players all pre-fetched via select_related)


def test_should_query_with_embedded_document(fixtures):
    class Query(graphene.ObjectType):
        professor_vector = graphene.Field(types.ProfessorVectorType, id=graphene.String())

        def resolve_professor_vector(self, info, id):
            return models.ProfessorVector.objects(metadata__id=id).first()

    query = """
        query {
          professorVector(id: "5e06aa20-6805-4eef-a144-5615dedbe32b") {
            vec
            metadata {
                firstName
            }
          }
        }
    """

    expected = {"professorVector": {"vec": [1.0, 2.3], "metadata": {"firstName": "Steven"}}}
    schema = graphene.Schema(query=Query, types=[types.ProfessorVectorType])
    result, count = execute_count(schema, query)
    assert not result.errors
    assert result.data == expected
    assert count == 1


def test_should_query_child(fixtures):
    class Query(graphene.ObjectType):
        children = graphene.List(types.ChildType)

        def resolve_children(self, *args, **kwargs):
            return list(models.Child.objects.all())

    query = """
        query Query {
            children {
                bar,
                baz,
                loc {
                     type,
                     coordinates
                }
            }
        }
    """
    expected = {
        "children": [
            {"bar": "BAR", "baz": "BAZ", "loc": None},
            {
                "bar": "bar",
                "baz": "baz",
                "loc": {"type": "Point", "coordinates": [10.0, 20.0]},
            },
        ]
    }

    schema = graphene.Schema(query=Query)
    result, count = execute_count(schema, query)
    assert not result.errors
    assert result.data == expected
    assert count == 1


def test_should_query_other_childs(fixtures):
    class Query(graphene.ObjectType):
        children = graphene.List(types.AnotherChildType)

        def resolve_children(self, *args, **kwargs):
            return list(models.AnotherChild.objects.all())

    query = """
        query Query {
            children {
                bar,
                qux,
                loc {
                     type,
                     coordinates
                }
            }
        }
    """
    expected = {
        "children": [
            {"bar": "BAR", "qux": "QUX", "loc": None},
            {
                "bar": "bar",
                "qux": "qux",
                "loc": {"type": "Point", "coordinates": [20, 10]},
            },
        ]
    }

    schema = graphene.Schema(query=Query)
    result, count = execute_count(schema, query)
    assert not result.errors
    assert result.data == expected
    assert count == 1


def test_should_query_all_childs(fixtures):
    class Query(graphene.ObjectType):
        children = graphene.List(types.ChildUnionType)

        def resolve_children(self, *args, **kwargs):
            return list(models.Parent.objects.all())

    query = """
        query Query {
            children {
                ... on ParentInterface {
                    bar
                }
                ... on ChildType{
                    baz
                    loc {
                        type,
                        coordinates
                    }
                }
                ... on AnotherChildType {
                    qux
                    loc {
                        type,
                        coordinates
                    }
                }
            }
        }
    """
    expected = {
        "children": [
            {"bar": "BAR", "qux": "QUX", "loc": None},
            {
                "bar": "bar",
                "qux": "qux",
                "loc": {
                    "type": "Point",
                    "coordinates": [20.0, 10.0],
                },
            },
            {"bar": "BAR", "baz": "BAZ", "loc": None},
            {
                "bar": "bar",
                "baz": "baz",
                "loc": {
                    "type": "Point",
                    "coordinates": [10.0, 20.0],
                },
            },
        ]
    }

    schema = graphene.Schema(query=Query)
    result, count = execute_count(schema, query)
    assert not result.errors
    assert result.data == expected
    assert count == 1


def test_should_query_cell_tower(fixtures):
    class Query(graphene.ObjectType):
        cell_towers = graphene.List(types.CellTowerType)

        def resolve_cell_towers(self, *args, **kwargs):
            return list(models.CellTower.objects.all())

    query = """
        query Query {
            cellTowers {
                code,
                base {
                    type,
                    coordinates
                },
                coverageArea {
                     type,
                     coordinates
                }
            }
        }
    """
    expected = {
        "cellTowers": [
            {
                "code": "bar",
                "base": {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [-43.36556, -22.99669],
                            [-43.36539, -23.01928],
                            [-43.26583, -23.01802],
                            [-43.36717, -22.98855],
                            [-43.36636, -22.99351],
                            [-43.36556, -22.99669],
                        ]
                    ],
                },
                "coverageArea": {
                    "type": "MultiPolygon",
                    "coordinates": [
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
                },
            }
        ]
    }

    schema = graphene.Schema(query=Query)
    result, count = execute_count(schema, query)
    assert not result.errors
    assert result.data == expected
    assert count == 1

def test_should_query_zoned_datetime(fixtures):
    from .nodes import EventNode
    from graphene_mongo.synchronous.fields import MongoengineConnectionField

    class Query(graphene.ObjectType):
        events = MongoengineConnectionField(EventNode)

    schema = graphene.Schema(query=Query, auto_camelcase=True)
    result = schema.execute(
        "{ events { edges { node { name startTime { utc tz } } } } }"
    )
    assert not result.errors, result.errors
    edges = result.data["events"]["edges"]
    assert len(edges) == 2
    names = {e["node"]["name"] for e in edges}
    assert names == {"Kolkata Summit", "New York Meetup"}
    for edge in edges:
        st = edge["node"]["startTime"]
        assert st["utc"] is not None
        assert st["tz"] in ("Asia/Kolkata", "America/New_York")


def test_should_filter_zoned_datetime_by_utc(fixtures):
    """Exact equality on ZonedDateTimeField filters against the stored utc subfield."""
    from .nodes import EventNode
    from graphene_mongo.synchronous.fields import MongoengineConnectionField

    class Query(graphene.ObjectType):
        events = MongoengineConnectionField(EventNode)

    schema = graphene.Schema(query=Query, auto_camelcase=True)
    # Kolkata Summit: 2024-06-15 14:30 IST = 2024-06-15 09:00:00 UTC (exact equality)
    result = schema.execute(
        '{ events(startTime: "2024-06-15T09:00:00+00:00") { edges { node { name startTime { tz } } } } }'
    )
    assert not result.errors, result.errors
    edges = result.data["events"]["edges"]
    assert len(edges) == 1
    assert edges[0]["node"]["name"] == "Kolkata Summit"
    assert edges[0]["node"]["startTime"]["tz"] == "Asia/Kolkata"


def test_should_filter_zoned_datetime_range(fixtures):
    """filter_fields gte/lte on ZonedDateTimeField compare against the utc subfield."""
    from graphene_mongo.synchronous.types import MongoengineObjectType
    from graphene_mongo.synchronous.fields import MongoengineConnectionField
    from .. import models as m

    class EventRangeNode(MongoengineObjectType):
        class Meta:
            model = m.Event
            interfaces = (graphene.relay.Node,)
            filter_fields = {"start_time": ["gte", "lte", "gt", "lt", "in"]}

    class Query(graphene.ObjectType):
        events = MongoengineConnectionField(EventRangeNode)

    schema = graphene.Schema(query=Query, auto_camelcase=True)

    # Both events: Kolkata=2024-06-15T09:00Z, NY=2024-09-01T13:00Z
    # gte 2024-07-01 → only NY Meetup (auto_camelcase: start_time__gte → startTime_Gte)
    result = schema.execute(
        '{ events(startTime_Gte: "2024-07-01T00:00:00+00:00") { edges { node { name } } } }'
    )
    assert not result.errors, result.errors
    names = [e["node"]["name"] for e in result.data["events"]["edges"]]
    assert names == ["New York Meetup"]

    # lte 2024-07-01 → only Kolkata Summit
    result = schema.execute(
        '{ events(startTime_Lte: "2024-07-01T00:00:00+00:00") { edges { node { name } } } }'
    )
    assert not result.errors, result.errors
    names = [e["node"]["name"] for e in result.data["events"]["edges"]]
    assert names == ["Kolkata Summit"]

    # in [kolkata-utc, ny-utc] → both events (list of datetimes)
    result = schema.execute(
        '{ events(startTime_In: ["2024-06-15T09:00:00+00:00", "2024-09-01T13:00:00+00:00"]) { edges { node { name } } } }'
    )
    assert not result.errors, result.errors
    names = {e["node"]["name"] for e in result.data["events"]["edges"]}
    assert names == {"Kolkata Summit", "New York Meetup"}
