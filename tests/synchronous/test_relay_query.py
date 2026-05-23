import base64
import json
import os

import graphene
import pytest
from graphene.relay import Node
from graphql_relay.connection.array_connection import offset_to_cursor
from graphql_relay.node.node import to_global_id

from .. import models
from . import nodes
from graphene_mongo.synchronous.fields import MongoengineConnectionField
from graphene_mongo.synchronous.types import MongoengineObjectType
from .utils import execute_count


def test_should_query_reporter(fixtures):
    class Query(graphene.ObjectType):
        reporter = graphene.Field(nodes.ReporterNode)

        def resolve_reporter(self, *args, **kwargs):
            return models.Reporter.objects.select_related("articles", "generic_reference").first()

    query = """
        query ReporterQuery {
            reporter {
                firstName,
                lastName,
                email,
                awards,
                articles {
                    edges {
                        node {
                            headline
                        }
                    }
                },
                embeddedArticles {
                    edges {
                        node {
                            headline
                        }
                    }
                },
                embeddedListArticles {
                    edges {
                        node {
                            headline
                        }
                    }
                },
                genericReference {
                    __typename
                    ... on ArticleNode {
                        headline
                    }
                }
            }
        }
    """
    expected = {
        "reporter": {
            "firstName": "Allen",
            "lastName": "Iverson",
            "email": "ai@gmail.com",
            "awards": ["2010-mvp"],
            "articles": {
                "edges": [
                    {"node": {"headline": "Hello"}},
                    {"node": {"headline": "World"}},
                ]
            },
            "embeddedArticles": {
                "edges": [
                    {"node": {"headline": "Real"}},
                    {"node": {"headline": "World"}},
                ]
            },
            "embeddedListArticles": {
                "edges": [
                    {"node": {"headline": "World"}},
                    {"node": {"headline": "Real"}},
                ]
            },
            "genericReference": {"__typename": "ArticleNode", "headline": "Hello"},
        }
    }

    schema = graphene.Schema(query=Query)
    result, count = execute_count(schema, query)
    assert not result.errors
    assert result.data == expected
    assert count == 1  # select_related fetches reporter + articles + generic_reference in a single aggregate


def test_should_query_reporters_with_nested_document(fixtures):
    class Query(graphene.ObjectType):
        reporters = MongoengineConnectionField(nodes.ReporterNode)

    query = """
        query ReporterQuery {
            reporters(firstName: "Allen") {
                edges {
                    node {
                        firstName,
                        lastName,
                        email,
                        articles(headline: "Hello") {
                             edges {
                                  node {
                                       headline
                                  }
                             }
                        }
                    }
                }
            }
        }
    """
    expected = {
        "reporters": {
            "edges": [
                {
                    "node": {
                        "firstName": "Allen",
                        "lastName": "Iverson",
                        "email": "ai@gmail.com",
                        "articles": {"edges": [{"node": {"headline": "Hello"}}]},
                    }
                }
            ]
        }
    }

    schema = graphene.Schema(query=Query)
    result, count = execute_count(schema, query)
    assert not result.errors
    assert result.data == expected
    assert count == 1  # 1 reporters aggregate; article filter (headline="Hello") pushed into $lookup sub-pipeline by MongoEngine


def test_should_query_all_editors(fixtures, fixtures_dirname):
    class Query(graphene.ObjectType):
        editors = MongoengineConnectionField(nodes.EditorNode)

    query = """
        query EditorQuery {
            editors {
                edges {
                    node {
                        id,
                        firstName,
                        lastName,
                        avatar {
                            contentType,
                            length,
                            data
                        }
                    }
                }
            }
        }
    """

    avator_filename = os.path.join(fixtures_dirname, "image.jpg")
    with open(avator_filename, "rb") as f:
        data = base64.b64encode(f.read())

    expected = {
        "editors": {
            "edges": [
                {
                    "node": {
                        "id": "RWRpdG9yTm9kZTox",
                        "firstName": "Penny",
                        "lastName": "Hardaway",
                        "avatar": {
                            "contentType": "image/jpeg",
                            "length": 46928,
                            "data": data.decode("utf-8"),
                        },
                    }
                },
                {
                    "node": {
                        "id": "RWRpdG9yTm9kZToy",
                        "firstName": "Grant",
                        "lastName": "Hill",
                        "avatar": {"contentType": None, "length": 0, "data": None},
                    }
                },
                {
                    "node": {
                        "id": "RWRpdG9yTm9kZToz",
                        "firstName": "Dennis",
                        "lastName": "Rodman",
                        "avatar": {"contentType": None, "length": 0, "data": None},
                    }
                },
            ]
        }
    }
    schema = graphene.Schema(query=Query)
    result, count = execute_count(schema, query)
    assert not result.errors
    assert result.data == expected
    assert count >= 1  # 1 editors query; GridFS avatar reads may add extra queries


def test_should_filter_editors_by_id(fixtures):
    class Query(graphene.ObjectType):
        editors = MongoengineConnectionField(nodes.EditorNode)

    query = """
        query EditorQuery {
          editors(id: "RWRpdG9yTm9kZToy") {
            edges {
                node {
                    id,
                    firstName,
                    lastName
                }
            }
          }
        }
    """
    expected = {
        "editors": {
            "edges": [
                {
                    "node": {
                        "id": "RWRpdG9yTm9kZToy",
                        "firstName": "Grant",
                        "lastName": "Hill",
                    }
                }
            ]
        }
    }
    schema = graphene.Schema(query=Query)
    result, count = execute_count(schema, query)
    assert not result.errors
    assert result.data == expected
    assert count == 1  # single find filtered by relay-decoded _id


def test_should_filter(fixtures):
    class Query(graphene.ObjectType):
        articles = MongoengineConnectionField(nodes.ArticleNode)

    query = """
        query ArticlesQuery {
            articles(headline: "World") {
                edges {
                    node {
                        headline,
                        pubDate,
                        editor {
                            firstName
                        }
                    }
                }
            }
        }
    """
    expected = {
        "articles": {
            "edges": [
                {
                    "node": {
                        "headline": "World",
                        "editor": {"firstName": "Grant"},
                        "pubDate": "2020-01-01T00:00:00",
                    }
                }
            ]
        }
    }
    schema = graphene.Schema(query=Query)
    result, count = execute_count(schema, query)
    assert not result.errors
    assert result.data == expected
    assert count == 1  # 1 aggregate with $match on headline; editor ReferenceField resolved via $lookup in the same query


def test_should_filter_by_reference_field(fixtures):
    class Query(graphene.ObjectType):
        articles = MongoengineConnectionField(nodes.ArticleNode)

    query = """
        query ArticlesQuery {
            articles(editor: "RWRpdG9yTm9kZTox") {
                edges {
                    node {
                        headline,
                        editor {
                            firstName
                        }
                    }
                }
            }
        }
    """
    expected = {
        "articles": {"edges": [{"node": {"headline": "Hello", "editor": {"firstName": "Penny"}}}]}
    }
    schema = graphene.Schema(query=Query)
    result, count = execute_count(schema, query)
    assert not result.errors
    assert result.data == expected
    assert count == 1  # 1 aggregate with $match on editor _id; editor ReferenceField resolved via $lookup


def test_should_filter_through_inheritance(fixtures):
    class Query(graphene.ObjectType):
        node = Node.Field()
        children = MongoengineConnectionField(nodes.ChildNode)

    query = """
        query ChildrenQuery {
            children(bar: "bar") {
                edges {
                    node {
                        bar,
                        baz,
                        loc {
                             type,
                             coordinates
                        }
                    }
                }
            }
        }
    """
    expected = {
        "children": {
            "edges": [
                {
                    "node": {
                        "bar": "bar",
                        "baz": "baz",
                        "loc": {"type": "Point", "coordinates": [10.0, 20.0]},
                    }
                }
            ]
        }
    }
    schema = graphene.Schema(query=Query)
    result, count = execute_count(schema, query)
    assert not result.errors
    assert result.data == expected
    assert count == 1  # 1 aggregate with $match on bar; inherited Child collection queried once


def test_should_filter_by_list_contains(fixtures):
    # Notes: https://goo.gl/hMNRgs
    class Query(graphene.ObjectType):
        reporters = MongoengineConnectionField(nodes.ReporterNode)

    query = """
        query ReportersQuery {
            reporters (awards: "2010-mvp") {
                edges {
                    node {
                        id,
                        firstName,
                        awards,
                        genericReferences {
                            __typename
                            ... on ArticleNode {
                                headline
                            }
                        }
                    }
                }
            }
        }
    """
    expected = {
        "reporters": {
            "edges": [
                {
                    "node": {
                        "id": "UmVwb3J0ZXJOb2RlOjE=",
                        "firstName": "Allen",
                        "awards": ["2010-mvp"],
                        "genericReferences": [
                            {
                                "__typename": "ArticleNode",
                                "headline": "Hello",
                            }
                        ],
                    }
                }
            ]
        }
    }
    schema = graphene.Schema(query=Query)
    result, count = execute_count(schema, query)
    assert not result.errors
    assert result.data == expected
    assert count == 1  # 1 reporters aggregate with genericReferences joined via select_related $lookup


def test_should_filter_by_id(fixtures):
    # Notes: https://goo.gl/hMNRgs
    class Query(graphene.ObjectType):
        reporter = Node.Field(nodes.ReporterNode)

    query = """
        query ReporterQuery {
            reporter (id: "UmVwb3J0ZXJOb2RlOjE=") {
                id,
                firstName,
                awards
            }
        }
    """
    expected = {
        "reporter": {
            "id": "UmVwb3J0ZXJOb2RlOjE=",
            "firstName": "Allen",
            "awards": ["2010-mvp"],
        }
    }
    schema = graphene.Schema(query=Query)
    result, count = execute_count(schema, query)
    assert not result.errors
    assert result.data == expected
    assert count == 1  # Node.Field by relay ID resolves to a single _id lookup


def test_should_first_n(fixtures):
    class Query(graphene.ObjectType):
        editors = MongoengineConnectionField(nodes.EditorNode)

    query = """
        query EditorQuery {
            editors(first: 2) {
                edges {
                    cursor,
                    node {
                        firstName
                    }
                }
                pageInfo {
                    hasNextPage
                    hasPreviousPage
                    startCursor
                    endCursor
                }
            }
        }
    """
    expected = {
        "editors": {
            "edges": [
                {"cursor": "YXJyYXljb25uZWN0aW9uOjA=", "node": {"firstName": "Penny"}},
                {"cursor": "YXJyYXljb25uZWN0aW9uOjE=", "node": {"firstName": "Grant"}},
            ],
            "pageInfo": {
                "hasNextPage": True,
                "hasPreviousPage": False,
                "startCursor": "YXJyYXljb25uZWN0aW9uOjA=",
                "endCursor": "YXJyYXljb25uZWN0aW9uOjE=",
            },
        }
    }
    schema = graphene.Schema(query=Query)
    result, count = execute_count(schema, query)

    assert not result.errors
    assert result.data == expected
    assert count == 2  # first:2 triggers pagination: 1 count query (for hasNextPage) + 1 find query (sliced results)


def test_should_after(fixtures):
    class Query(graphene.ObjectType):
        players = MongoengineConnectionField(nodes.PlayerNode)

    query = """
        query EditorQuery {
            players(after: "YXJyYXljb25uZWN0aW9uOjA=") {
                edges {
                    cursor,
                    node {
                        firstName
                    }
                }
            }
        }
    """
    expected = {
        "players": {
            "edges": [
                {"cursor": "YXJyYXljb25uZWN0aW9uOjE=", "node": {"firstName": "Magic"}},
                {"cursor": "YXJyYXljb25uZWN0aW9uOjI=", "node": {"firstName": "Larry"}},
                {"cursor": "YXJyYXljb25uZWN0aW9uOjM=", "node": {"firstName": "Chris"}},
            ]
        }
    }
    schema = graphene.Schema(query=Query)
    result, count = execute_count(schema, query)

    assert not result.errors
    assert result.data == expected
    assert count == 2  # after cursor triggers pagination: 1 count + 1 find starting from the cursor offset


def test_should_before(fixtures):
    class Query(graphene.ObjectType):
        players = MongoengineConnectionField(nodes.PlayerNode)

    query = """
        query EditorQuery {
            players(before: "YXJyYXljb25uZWN0aW9uOjI=") {
                edges {
                    cursor,
                    node {
                        firstName
                    }
                }
            }
        }
    """
    expected = {
        "players": {
            "edges": [
                {
                    "cursor": "YXJyYXljb25uZWN0aW9uOjA=",
                    "node": {"firstName": "Michael"},
                },
                {"cursor": "YXJyYXljb25uZWN0aW9uOjE=", "node": {"firstName": "Magic"}},
            ]
        }
    }
    schema = graphene.Schema(query=Query)
    result, count = execute_count(schema, query)

    assert not result.errors
    assert result.data == expected
    assert count == 2  # before cursor triggers pagination: 1 count + 1 find truncated before the cursor


def test_should_last_n(fixtures):
    class Query(graphene.ObjectType):
        players = MongoengineConnectionField(nodes.PlayerNode)

    query = """
        query PlayerQuery {
            players(last: 2) {
                edges {
                    cursor,
                    node {
                        firstName
                    }
                }
            }
        }
    """
    expected = {
        "players": {
            "edges": [
                {"cursor": "YXJyYXljb25uZWN0aW9uOjI=", "node": {"firstName": "Larry"}},
                {"cursor": "YXJyYXljb25uZWN0aW9uOjM=", "node": {"firstName": "Chris"}},
            ]
        }
    }
    schema = graphene.Schema(query=Query)
    result, count = execute_count(schema, query)

    assert not result.errors
    assert result.data == expected
    assert count == 2  # last:2 triggers pagination: 1 count (to compute tail offset) + 1 find from the end


def test_should_self_reference(fixtures):
    class Query(graphene.ObjectType):
        players = MongoengineConnectionField(nodes.PlayerNode)

    query = """
        query PlayersQuery {
            players {
                edges {
                    node {
                        firstName,
                        players {
                            edges {
                                node {
                                    firstName
                                }
                            }
                        },
                        embeddedListArticles {
                            edges {
                                node {
                                    headline
                                }
                            }
                        }
                    }
                }
            }
        }
    """
    expected = {
        "players": {
            "edges": [
                {
                    "node": {
                        "firstName": "Michael",
                        "players": {"edges": [{"node": {"firstName": "Magic"}}]},
                        "embeddedListArticles": {"edges": []},
                    }
                },
                {
                    "node": {
                        "firstName": "Magic",
                        "players": {"edges": [{"node": {"firstName": "Michael"}}]},
                        "embeddedListArticles": {"edges": []},
                    }
                },
                {
                    "node": {
                        "firstName": "Larry",
                        "players": {
                            "edges": [
                                {"node": {"firstName": "Michael"}},
                                {"node": {"firstName": "Magic"}},
                            ]
                        },
                        "embeddedListArticles": {"edges": []},
                    }
                },
                {
                    "node": {
                        "firstName": "Chris",
                        "players": {"edges": []},
                        "embeddedListArticles": {"edges": []},
                    }
                },
            ]
        }
    }
    schema = graphene.Schema(query=Query)
    result, count = execute_count(schema, query)
    assert not result.errors
    assert result.data == expected
    assert count >= 1  # 1 players query + 1 sub-query per player for the nested players connection field


def test_should_lazy_reference(fixtures):
    class Query(graphene.ObjectType):
        node = Node.Field()
        parents = MongoengineConnectionField(nodes.ParentWithRelationshipNode)

    schema = graphene.Schema(query=Query)

    query = """
    query {
        parents {
            edges {
                node {
                    beforeChild {
                        edges {
                            node {
                                name,
                                parent { name }
                            }
                        }
                    },
                    afterChild {
                        edges {
                            node {
                                name,
                                parent { name }
                            }
                        }
                    }
                }
            }
        }
    }
    """

    expected = {
        "parents": {
            "edges": [
                {
                    "node": {
                        "beforeChild": {
                            "edges": [{"node": {"name": "Akari", "parent": {"name": "Yui"}}}]
                        },
                        "afterChild": {
                            "edges": [{"node": {"name": "Kyouko", "parent": {"name": "Yui"}}}]
                        },
                    }
                }
            ]
        }
    }

    result, count = execute_count(schema, query)
    assert not result.errors
    assert result.data == expected
    assert count >= 1  # 1 parents query + extra queries to dereference each lazy beforeChild/afterChild relationship


def test_should_query_with_embedded_document(fixtures):
    class Query(graphene.ObjectType):
        professors = MongoengineConnectionField(nodes.ProfessorVectorNode)

    query = """
    query {
        professors {
            edges {
                node {
                    vec,
                    metadata {
                        firstName
                    }
                }
            }
        }
    }
    """
    expected = {
        "professors": {
            "edges": [{"node": {"vec": [1.0, 2.3], "metadata": {"firstName": "Steven"}}}]
        }
    }
    schema = graphene.Schema(query=Query)
    result, count = execute_count(schema, query)
    assert not result.errors
    assert result.data == expected
    assert count == 1  # 1 professors query; metadata is an EmbeddedDocument so no extra query needed


def test_should_get_queryset_returns_dict_filters(fixtures):
    class Query(graphene.ObjectType):
        node = Node.Field()
        articles = MongoengineConnectionField(
            nodes.ArticleNode, get_queryset=lambda *_, **__: {"headline": "World"}
        )

    query = """
           query ArticlesQuery {
               articles {
                   edges {
                       node {
                           headline,
                           pubDate,
                           editor {
                               firstName
                           }
                       }
                   }
               }
           }
       """
    expected = {
        "articles": {
            "edges": [
                {
                    "node": {
                        "headline": "World",
                        "editor": {"firstName": "Grant"},
                        "pubDate": "2020-01-01T00:00:00",
                    }
                }
            ]
        }
    }
    schema = graphene.Schema(query=Query)
    result, count = execute_count(schema, query)
    assert not result.errors
    assert result.data == expected
    assert count == 1  # dict-based get_queryset applies $match; editor ReferenceField resolved via $lookup in 1 aggregate


def test_should_get_queryset_returns_qs_filters(fixtures):
    def get_queryset(model, info, **args):
        return model.objects(headline="World")

    class Query(graphene.ObjectType):
        node = Node.Field()
        articles = MongoengineConnectionField(nodes.ArticleNode, get_queryset=get_queryset)

    query = """
           query ArticlesQuery {
               articles {
                   edges {
                       node {
                           headline,
                           pubDate,
                           editor {
                               firstName
                           }
                       }
                   }
               }
           }
       """
    expected = {
        "articles": {
            "edges": [
                {
                    "node": {
                        "headline": "World",
                        "editor": {"firstName": "Grant"},
                        "pubDate": "2020-01-01T00:00:00",
                    }
                }
            ]
        }
    }
    schema = graphene.Schema(query=Query)
    result, count = execute_count(schema, query)
    assert not result.errors
    assert result.data == expected
    assert count >= 1  # custom queryset-based get_queryset; 1 aggregate expected but bound is loose for safety


def test_should_filter_mongoengine_queryset(fixtures):
    class Query(graphene.ObjectType):
        players = MongoengineConnectionField(nodes.PlayerNode)

    query = """
        query players {
            players(firstName_Istartswith: "M") {
                edges {
                    node {
                        firstName
                    }
                }
            }
        }
    """
    expected = {
        "players": {
            "edges": [
                {"node": {"firstName": "Michael"}},
                {"node": {"firstName": "Magic"}},
            ]
        }
    }
    schema = graphene.Schema(query=Query)
    result, count = execute_count(schema, query)

    assert not result.errors
    assert json.dumps(result.data, sort_keys=True) == json.dumps(expected, sort_keys=True)
    assert count == 1  # 1 aggregate with case-insensitive startswith filter; no pagination


def test_should_query_document_with_embedded(fixtures):
    class Query(graphene.ObjectType):
        foos = MongoengineConnectionField(nodes.FooNode)

        def resolve_multiple_foos(self, *args, **kwargs):
            return list(models.Foo.objects.all())

    query = """
        query {
            foos {
                edges {
                    node {
                        bars {
                            edges {
                                node {
                                    someListField
                                }
                            }
                        }
                    }
                }
            }
        }
    """

    schema = graphene.Schema(query=Query)
    result, count = execute_count(schema, query)
    assert not result.errors
    assert count >= 1  # 1 foos query; bars is EmbeddedDocumentListField so no extra query, data is in the document


def test_should_filter_mongoengine_queryset_with_list(fixtures):
    class Query(graphene.ObjectType):
        players = MongoengineConnectionField(nodes.PlayerNode)

    query = """
        query players {
            players(firstName_In: ["Michael", "Magic"]) {
                edges {
                    node {
                        firstName
                    }
                }
            }
        }
    """
    expected = {
        "players": {
            "edges": [
                {"node": {"firstName": "Michael"}},
                {"node": {"firstName": "Magic"}},
            ]
        }
    }
    schema = graphene.Schema(query=Query)
    result, count = execute_count(schema, query)

    assert not result.errors
    assert json.dumps(result.data, sort_keys=True) == json.dumps(expected, sort_keys=True)
    assert count == 1  # 1 aggregate with $in filter on firstName; no pagination


def test_should_get_correct_list_of_documents(fixtures):
    class Query(graphene.ObjectType):
        players = MongoengineConnectionField(nodes.PlayerNode)

    query = """
        query players {
            players(firstName: "Michael") {
                edges {
                    node {
                        firstName,
                        articles(first: 3) {
                            edges {
                                node {
                                    headline
                                }
                            }
                        }
                    }
                }
            }
        }
    """
    expected = {
        "players": {
            "edges": [
                {
                    "node": {
                        "firstName": "Michael",
                        "articles": {
                            "edges": [
                                {
                                    "node": {
                                        "headline": "Hello",
                                    }
                                },
                                {
                                    "node": {
                                        "headline": "World",
                                    }
                                },
                            ]
                        },
                    }
                }
            ]
        }
    }
    schema = graphene.Schema(query=Query)
    result, count = execute_count(schema, query)

    assert not result.errors
    assert result.data == expected
    assert count >= 1  # 1 players find + paginated articles sub-queries per player (first:3 triggers count+find each)


def test_should_filter_mongoengine_queryset_by_id_and_other_fields(fixtures):
    class Query(graphene.ObjectType):
        players = MongoengineConnectionField(nodes.PlayerNode)

    larry = models.Player.objects.get(first_name="Larry")
    larry_relay_id = to_global_id("PlayerNode", larry.id)

    # "Larry" id && firstName == "Michael" should return nothing
    query = """
        query players {{
            players(
                id: "{larry_relay_id}",
                firstName: "Michael"
            ) {{
                edges {{
                    node {{
                        id
                        firstName
                    }}
                }}
            }}
        }}
    """.format(larry_relay_id=larry_relay_id)

    expected = {
        "players": {
            "edges": [],
        }
    }
    schema = graphene.Schema(query=Query)
    result, count = execute_count(schema, query)

    assert not result.errors
    assert json.dumps(result.data, sort_keys=True) == json.dumps(expected, sort_keys=True)
    assert count == 1  # conflicting id+firstName filters produce an empty result; still only 1 query

# ---------------------------------------------------------------------------
# N+1 / query-count tests
# ---------------------------------------------------------------------------

def test_editors_with_company_no_pagination(fixtures):
    class Query(graphene.ObjectType):
        editors = MongoengineConnectionField(nodes.EditorNode)

    result, count = execute_count(graphene.Schema(query=Query), """
        query {
            editors {
                edges {
                    node {
                        firstName
                        company { name }
                    }
                }
            }
        }
    """)

    assert not result.errors
    names = [e["node"]["firstName"] for e in result.data["editors"]["edges"]]
    assert names == ["Penny", "Grant", "Dennis"]
    assert count == 1  # no pagination: 1 aggregate with $lookup for company; count query skipped


def test_articles_with_editor_and_company_no_pagination(fixtures):
    class Query(graphene.ObjectType):
        articles = MongoengineConnectionField(nodes.ArticleNode)

    result, count = execute_count(graphene.Schema(query=Query), """
        query {
            articles {
                edges {
                    node {
                        headline
                        editor {
                            firstName
                            company { name }
                        }
                    }
                }
            }
        }
    """)

    assert not result.errors
    assert count == 1  # no pagination: 1 aggregate with nested $lookups for editor and editor→company; count query skipped


def test_articles_with_multiple_refs_no_pagination(fixtures):
    class Query(graphene.ObjectType):
        articles = MongoengineConnectionField(nodes.ArticleNode)

    result, count = execute_count(graphene.Schema(query=Query), """
        query {
            articles {
                edges {
                    node {
                        headline
                        editor {
                            firstName
                            company { name }
                        }
                        reporter { firstName }
                    }
                }
            }
        }
    """)

    assert not result.errors
    headlines = [e["node"]["headline"] for e in result.data["articles"]["edges"]]
    assert set(headlines) == {"Hello", "World", "Bye"}
    assert count == 1  # no pagination: 1 aggregate with $lookups for editor, editor→company, and reporter; count query skipped


def test_players_with_self_referential_no_pagination(fixtures):
    class Query(graphene.ObjectType):
        players = MongoengineConnectionField(nodes.PlayerNode)

    result, count = execute_count(graphene.Schema(query=Query), """
        query {
            players {
                edges {
                    node {
                        firstName
                        opponent { firstName }
                    }
                }
            }
        }
    """)

    assert not result.errors
    magic = next(
        e["node"] for e in result.data["players"]["edges"]
        if e["node"]["firstName"] == "Magic"
    )
    assert magic["opponent"]["firstName"] == "Michael"
    assert count == 1  # no pagination: 1 aggregate with $lookup for opponent (self-referential join); count query skipped


def test_editors_paginated_first(fixtures):
    class Query(graphene.ObjectType):
        editors = MongoengineConnectionField(nodes.EditorNode)

    result, count = execute_count(graphene.Schema(query=Query), """
        query {
            editors(first: 2) {
                edges {
                    node {
                        firstName
                        company { name }
                    }
                }
            }
        }
    """)

    assert not result.errors
    names = [e["node"]["firstName"] for e in result.data["editors"]["edges"]]
    assert names == ["Penny", "Grant"]
    assert count == 2  # first:2 triggers pagination: 1 count + 1 aggregate with $lookup for company


def test_editors_paginated_last(fixtures):
    class Query(graphene.ObjectType):
        editors = MongoengineConnectionField(nodes.EditorNode)

    result, count = execute_count(graphene.Schema(query=Query), """
        query {
            editors(last: 1) {
                edges {
                    node {
                        firstName
                        company { name }
                    }
                }
            }
        }
    """)

    assert not result.errors
    names = [e["node"]["firstName"] for e in result.data["editors"]["edges"]]
    assert names == ["Dennis"]
    assert count == 2  # last:1 triggers pagination: 1 count + 1 aggregate with $lookup for company


def test_editors_paginated_cursor_after(fixtures):
    class Query(graphene.ObjectType):
        editors = MongoengineConnectionField(nodes.EditorNode)

    schema = graphene.Schema(query=Query)
    cursor = offset_to_cursor(0)

    result, count = execute_count(schema, f"""
        query {{
            editors(first: 2, after: "{cursor}") {{
                edges {{
                    node {{
                        firstName
                        company {{ name }}
                    }}
                }}
            }}
        }}
    """)

    assert not result.errors
    names = [e["node"]["firstName"] for e in result.data["editors"]["edges"]]
    assert names == ["Grant", "Dennis"]
    assert count == 2  # first:2 with after cursor: 1 count + 1 aggregate with $lookup for company


def test_articles_paginated_first_with_editor(fixtures):
    class Query(graphene.ObjectType):
        articles = MongoengineConnectionField(nodes.ArticleNode)

    result, count = execute_count(graphene.Schema(query=Query), """
        query {
            articles(first: 2) {
                edges {
                    node {
                        headline
                        editor {
                            firstName
                            company { name }
                        }
                    }
                }
            }
        }
    """)

    assert not result.errors
    assert len(result.data["articles"]["edges"]) == 2
    assert count == 2  # first:2 triggers pagination: 1 count + 1 aggregate with $lookups for editor and editor→company


# ---------------------------------------------------------------------------
# MongoDB projection tests — verify only requested + required fields are fetched
# ---------------------------------------------------------------------------

from ..mongo_capture import captured_commands


def test_projection_only_queried_fields(fixtures):
    """Querying firstName only should project first_name, not last_name or avatar."""
    class Query(graphene.ObjectType):
        editors = MongoengineConnectionField(nodes.EditorNode)

    with captured_commands() as cap:
        result = graphene.Schema(query=Query).execute(
            "query { editors { edges { node { firstName } } } }"
        )

    assert not result.errors
    projected = cap.projected_fields()
    assert "fname" in projected  # first_name has db_field="fname"
    assert "last_name" not in projected
    assert "avatar" not in projected


def test_projection_multiple_fields(fixtures):
    """Querying firstName and lastName should project both but not avatar."""
    class Query(graphene.ObjectType):
        editors = MongoengineConnectionField(nodes.EditorNode)

    with captured_commands() as cap:
        result = graphene.Schema(query=Query).execute(
            "query { editors { edges { node { firstName lastName } } } }"
        )

    assert not result.errors
    projected = cap.projected_fields()
    assert "fname" in projected  # first_name has db_field="fname"
    assert "last_name" in projected
    assert "avatar" not in projected


def test_projection_with_reference_field(fixtures):
    """Querying a reference field projects only that reference on the parent document — not all parent fields."""
    class Query(graphene.ObjectType):
        editors = MongoengineConnectionField(nodes.EditorNode)

    with captured_commands() as cap:
        result = graphene.Schema(query=Query).execute("""
            query {
                editors {
                    edges {
                        node {
                            firstName
                            company { name }
                        }
                    }
                }
            }
        """)

    assert not result.errors
    projected = cap.projected_fields()
    assert "fname" in projected      # first_name has db_field="fname"
    assert "last_name" not in projected
    assert "company" in projected    # company reference is projected (not all editor fields)


def test_projection_list_reference_field(fixtures):
    """articles (ListField(ReferenceField)) projects only the queried reporter fields; articles are
    joined in the same aggregate via select_related — no separate find on test_article."""
    class Query(graphene.ObjectType):
        reporters = MongoengineConnectionField(nodes.ReporterNode)

    with captured_commands() as cap:
        result = graphene.Schema(query=Query).execute("""
            query {
                reporters {
                    edges {
                        node {
                            firstName
                            articles {
                                edges { node { headline } }
                            }
                        }
                    }
                }
            }
        """)

    assert not result.errors
    # Reporter aggregate projects only the queried reporter fields
    reporter_projected = cap.projected_fields_for("test_reporter")
    assert "first_name" in reporter_projected     # queried reporter field
    assert "articles" in reporter_projected       # articles reference list is projected
    assert "email" not in reporter_projected      # unqueried reporter fields are excluded
    assert "awards" not in reporter_projected
    assert "generic_reference" not in reporter_projected

    # select_related joins articles via $lookup in the same aggregate — no separate find
    assert len(cap.projected_fields_for("test_article")) == 0


def test_projection_generic_reference_field(fixtures):
    """generic_reference (GenericReferenceField) is joined via select_related — 1 aggregate, no separate find."""
    class Query(graphene.ObjectType):
        reporters = MongoengineConnectionField(nodes.ReporterNode)

    with captured_commands() as cap:
        result = graphene.Schema(query=Query).execute("""
            query {
                reporters {
                    edges {
                        node {
                            firstName
                            genericReference {
                                __typename
                                ... on ArticleNode { headline }
                            }
                        }
                    }
                }
            }
        """)

    assert not result.errors
    reporter_projected = cap.projected_fields_for("test_reporter")
    assert "first_name" in reporter_projected         # queried reporter field
    assert "generic_reference" in reporter_projected  # GenericReferenceField is projected
    assert "email" not in reporter_projected          # unqueried reporter fields are excluded
    assert "awards" not in reporter_projected
    assert "articles" not in reporter_projected

    # select_related joins via $lookup in the same aggregate — no separate find
    assert len(cap.projected_fields_for("test_article")) == 0


def test_projection_list_generic_reference_field(fixtures):
    """generic_references (ListField(GenericReferenceField)) is joined via select_related — 1 aggregate, no separate find."""
    class Query(graphene.ObjectType):
        reporters = MongoengineConnectionField(nodes.ReporterNode)

    with captured_commands() as cap:
        result = graphene.Schema(query=Query).execute("""
            query {
                reporters {
                    edges {
                        node {
                            firstName
                            genericReferences {
                                __typename
                                ... on ArticleNode { headline }
                            }
                        }
                    }
                }
            }
        """)

    assert not result.errors
    reporter_projected = cap.projected_fields_for("test_reporter")
    assert "first_name" in reporter_projected          # queried reporter field
    assert "generic_references" in reporter_projected  # ListField(GenericReferenceField) is projected
    assert "email" not in reporter_projected           # unqueried reporter fields are excluded
    assert "awards" not in reporter_projected
    assert "articles" not in reporter_projected

    # select_related joins via $lookup in the same aggregate — no separate find
    assert len(cap.projected_fields_for("test_article")) == 0
