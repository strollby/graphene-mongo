import base64
import json
import os

import graphene

from .. import models
from . import types as async_types
from .utils import execute_count


async def test_should_query_editor(fixtures, fixtures_dirname):
    class Query(graphene.ObjectType):
        editor = graphene.Field(async_types.EditorAsyncType)
        editors = graphene.List(async_types.EditorAsyncType)

        async def resolve_editor(self, *args, **kwargs):
            return await models.Editor.aobjects.select_related("company").first()

        async def resolve_editors(self, *args, **kwargs):
            return await models.Editor.aobjects.all().to_list()

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

    avatar_filename = os.path.join(fixtures_dirname, "image.jpg")
    with open(avatar_filename, "rb") as f:
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
    result, count = await execute_count(schema, query)
    assert not result.errors
    metadata = result.data["editor"].pop("metadata")
    assert json.loads(metadata) == expected_metadata
    assert result.data == expected
    assert (
        count == 4
    )  # 1 first editor (company pre-fetched via select_related) + 2 GridFS reads (files+chunks) + 1 all editors


async def test_should_query_reporter(fixtures):
    class Query(graphene.ObjectType):
        reporter = graphene.Field(async_types.ReporterAsyncType)

        async def resolve_reporter(self, *args, **kwargs):
            return await models.Reporter.aobjects.select_related("articles").first()

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
    result, count = await execute_count(schema, query)
    assert not result.errors
    assert result.data == expected
    assert count == 1


async def test_should_custom_kwargs(fixtures):
    class Query(graphene.ObjectType):
        editors = graphene.List(async_types.EditorAsyncType, first=graphene.Int())

        async def resolve_editors(self, *args, **kwargs):
            editors = await models.Editor.aobjects.all().to_list()
            if "first" in kwargs:
                editors = editors[: kwargs["first"]]
            return editors

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
    result, count = await execute_count(schema, query)
    assert not result.errors
    assert result.data == expected
    assert count == 1


async def test_should_self_reference(fixtures):
    class Query(graphene.ObjectType):
        all_players = graphene.List(async_types.PlayerAsyncType)

        async def resolve_all_players(self, *args, **kwargs):
            return await models.Player.aobjects.select_related("players", "opponent").to_list()

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
    result, count = await execute_count(schema, query)
    assert not result.errors
    assert result.data == expected
    assert (
        count == 1
    )  # 1 select_related aggregate (opponent + players all pre-fetched via select_related)


async def test_should_query_with_embedded_document(fixtures):
    class Query(graphene.ObjectType):
        professor_vector = graphene.Field(
            async_types.ProfessorVectorAsyncType, id=graphene.String()
        )

        async def resolve_professor_vector(self, info, id):
            return await models.ProfessorVector.aobjects(metadata__id=id).first()

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
    schema = graphene.Schema(query=Query, types=[async_types.ProfessorVectorAsyncType])
    result, count = await execute_count(schema, query)
    assert not result.errors
    assert result.data == expected
    assert count == 1


async def test_should_query_child(fixtures):
    class Query(graphene.ObjectType):
        children = graphene.List(async_types.ChildAsyncType)

        async def resolve_children(self, *args, **kwargs):
            return await models.Child.aobjects.all().to_list()

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
    result, count = await execute_count(schema, query)
    assert not result.errors
    assert result.data == expected
    assert count == 1


async def test_should_query_other_childs(fixtures):
    class Query(graphene.ObjectType):
        children = graphene.List(async_types.AnotherChildAsyncType)

        async def resolve_children(self, *args, **kwargs):
            return await models.AnotherChild.aobjects.all().to_list()

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
    result, count = await execute_count(schema, query)
    assert not result.errors
    assert result.data == expected
    assert count == 1


async def test_should_query_all_childs(fixtures):
    class Query(graphene.ObjectType):
        children = graphene.List(async_types.ChildAsyncUnionType)

        async def resolve_children(self, *args, **kwargs):
            return await models.Parent.aobjects.all().to_list()

    query = """
        query Query {
            children {
                ... on ParentAsyncInterface {
                    bar
                }
                ... on ChildAsyncType {
                    baz
                    loc {
                        type,
                        coordinates
                    }
                }
                ... on AnotherChildAsyncType {
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
                "loc": {"type": "Point", "coordinates": [20.0, 10.0]},
            },
            {"bar": "BAR", "baz": "BAZ", "loc": None},
            {
                "bar": "bar",
                "baz": "baz",
                "loc": {"type": "Point", "coordinates": [10.0, 20.0]},
            },
        ]
    }

    schema = graphene.Schema(query=Query)
    result, count = await execute_count(schema, query)
    assert not result.errors
    assert result.data == expected
    assert count == 1


async def test_should_query_cell_tower(fixtures):
    class Query(graphene.ObjectType):
        cell_towers = graphene.List(async_types.CellTowerAsyncType)

        async def resolve_cell_towers(self, *args, **kwargs):
            return await models.CellTower.aobjects.all().to_list()

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
    result, count = await execute_count(schema, query)
    assert not result.errors
    assert result.data == expected
    assert count == 1


async def test_should_query_aware_datetime(fixtures):
    from .nodes import EventAsyncNode
    from graphene_mongo import AsyncMongoengineConnectionField

    class Query(graphene.ObjectType):
        events = AsyncMongoengineConnectionField(EventAsyncNode)

    schema = graphene.Schema(query=Query, auto_camelcase=True)
    result = await schema.execute_async("{ events { edges { node { name startTime } } } }")
    assert not result.errors, result.errors
    edges = result.data["events"]["edges"]
    assert len(edges) == 2
    by_name = {e["node"]["name"]: e["node"]["startTime"] for e in edges}
    # IXDTF format: local wall-clock time + offset + [IANA annotation]
    assert by_name["Kolkata Summit"] == "2024-06-15T14:30:00+05:30[Asia/Kolkata]"
    assert by_name["New York Meetup"] == "2024-09-01T09:00:00-04:00[America/New_York]"


async def test_should_filter_aware_datetime_by_utc(fixtures):
    """Exact equality on AwareDateTimeField using IXDTF input."""
    from .nodes import EventAsyncNode
    from graphene_mongo import AsyncMongoengineConnectionField

    class Query(graphene.ObjectType):
        events = AsyncMongoengineConnectionField(EventAsyncNode)

    schema = graphene.Schema(query=Query, auto_camelcase=True)
    # Filter using local IXDTF string — Kolkata Summit is 2024-06-15 14:30 IST
    result = await schema.execute_async(
        '{ events(startTime: "2024-06-15T14:30:00+05:30[Asia/Kolkata]") { edges { node { name startTime } } } }'
    )
    assert not result.errors, result.errors
    edges = result.data["events"]["edges"]
    assert len(edges) == 1
    assert edges[0]["node"]["name"] == "Kolkata Summit"
    assert edges[0]["node"]["startTime"] == "2024-06-15T14:30:00+05:30[Asia/Kolkata]"


async def test_should_filter_aware_datetime_range(fixtures):
    """filter_fields gte/lte/in on AwareDateTimeField compare against the utc subfield."""
    from graphene_mongo.asynchronous.types import AsyncMongoengineObjectType
    from graphene_mongo import AsyncMongoengineConnectionField
    from .. import models as m

    class EventRangeAsyncNode(AsyncMongoengineObjectType):
        class Meta:
            model = m.Event
            interfaces = (graphene.relay.Node,)
            filter_fields = {"start_time": ["gte", "lte", "gt", "lt", "in"]}

    class Query(graphene.ObjectType):
        events = AsyncMongoengineConnectionField(EventRangeAsyncNode)

    schema = graphene.Schema(query=Query, auto_camelcase=True)

    # gte 2024-07-01 UTC → only NY Meetup (plain UTC offset, no IANA annotation)
    result = await schema.execute_async(
        '{ events(startTime_Gte: "2024-07-01T00:00:00+00:00") { edges { node { name } } } }'
    )
    assert not result.errors, result.errors
    names = [e["node"]["name"] for e in result.data["events"]["edges"]]
    assert names == ["New York Meetup"]

    # lte using plain offset → only Kolkata Summit
    result = await schema.execute_async(
        '{ events(startTime_Lte: "2024-07-01T00:00:00+00:00") { edges { node { name } } } }'
    )
    assert not result.errors, result.errors
    names = [e["node"]["name"] for e in result.data["events"]["edges"]]
    assert names == ["Kolkata Summit"]

    # in using IXDTF strings → both events
    result = await schema.execute_async(
        '{ events(startTime_In: ["2024-06-15T14:30:00+05:30[Asia/Kolkata]", "2024-09-01T09:00:00-04:00[America/New_York]"]) { edges { node { name } } } }'
    )
    assert not result.errors, result.errors
    names = {e["node"]["name"] for e in result.data["events"]["edges"]}
    assert names == {"Kolkata Summit", "New York Meetup"}
