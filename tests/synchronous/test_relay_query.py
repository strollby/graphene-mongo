import base64
import json
import os

import graphene
from graphene.relay import Node
from graphql_relay.connection.array_connection import offset_to_cursor
from graphql_relay.node.node import to_global_id

from .. import models
from . import nodes
from graphene_mongo.synchronous.fields import MongoengineConnectionField
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
    assert (
        count == 1
    )  # select_related fetches reporter + articles + generic_reference in a single aggregate


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
    assert (
        count == 1
    )  # 1 reporters aggregate; article filter (headline="Hello") pushed into $lookup sub-pipeline by MongoEngine


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
    assert count == 3  # 1 editors find + 2 GridFS reads (files + chunks) for Penny's avatar


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
    assert (
        count == 1
    )  # 1 aggregate with $match on headline; editor ReferenceField resolved via $lookup in the same query


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
    assert (
        count == 1
    )  # 1 aggregate with $match on editor _id; editor ReferenceField resolved via $lookup


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
    assert (
        count == 1
    )  # 1 reporters aggregate with genericReferences joined via select_related $lookup


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
    assert (
        count == 2
    )  # first:2 triggers pagination: 1 count query (for hasNextPage) + 1 find query (sliced results)


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
    assert (
        count == 1
    )  # after cursor: no count query needed (last is None, pageInfo not requested); 1 find with skip


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
    assert (
        count == 1
    )  # before cursor: no count query needed (last is None, pageInfo not requested); 1 find with limit


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
    assert (
        count == 2
    )  # last:2 triggers pagination: 1 count (to compute tail offset) + 1 find from the end


def test_should_after_with_page_info(fixtures):
    """after + pageInfo forces a count query (needed for hasPreviousPage/hasNextPage)."""

    class Query(graphene.ObjectType):
        players = MongoengineConnectionField(nodes.PlayerNode)

    query = """
        query {
            players(after: "YXJyYXljb25uZWN0aW9uOjA=") {
                edges {
                    cursor
                    node { firstName }
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
    schema = graphene.Schema(query=Query)
    result, count = execute_count(schema, query)

    assert not result.errors
    edges = result.data["players"]["edges"]
    assert [e["node"]["firstName"] for e in edges] == ["Magic", "Larry", "Chris"]
    assert result.data["players"]["pageInfo"]["hasPreviousPage"] is True
    assert count == 2  # pageInfo requested: count query issued even though last is not set


def test_should_before_with_page_info(fixtures):
    """before + pageInfo forces a count query (needed for hasNextPage)."""

    class Query(graphene.ObjectType):
        players = MongoengineConnectionField(nodes.PlayerNode)

    query = """
        query {
            players(before: "YXJyYXljb25uZWN0aW9uOjI=") {
                edges {
                    cursor
                    node { firstName }
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
    schema = graphene.Schema(query=Query)
    result, count = execute_count(schema, query)

    assert not result.errors
    edges = result.data["players"]["edges"]
    assert [e["node"]["firstName"] for e in edges] == ["Michael", "Magic"]
    assert result.data["players"]["pageInfo"]["hasNextPage"] is True
    assert result.data["players"]["pageInfo"]["hasPreviousPage"] is False
    assert count == 2  # pageInfo requested: count query issued even though last is not set


def test_should_first_without_page_info(fixtures):
    """first without pageInfo skips the count query entirely."""

    class Query(graphene.ObjectType):
        players = MongoengineConnectionField(nodes.PlayerNode)

    query = """
        query {
            players(first: 2) {
                edges {
                    node { firstName }
                }
            }
        }
    """
    schema = graphene.Schema(query=Query)
    result, count = execute_count(schema, query)

    assert not result.errors
    assert [e["node"]["firstName"] for e in result.data["players"]["edges"]] == ["Michael", "Magic"]
    assert count == 1  # no pageInfo: count query skipped; 1 find with limit


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
    assert (
        count == 1
    )  # 1 players aggregate via select_related; nested players sub-connection resolved from pre-loaded list


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
    assert (
        count == 1
    )  # 1 aggregate (before_child, before_child.parent, after_child, after_child.parent all pre-fetched)


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
    assert (
        count == 1
    )  # 1 professors query; metadata is an EmbeddedDocument so no extra query needed


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
    assert (
        count == 1
    )  # dict-based get_queryset applies $match; editor ReferenceField resolved via $lookup in 1 aggregate


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
    assert (
        count == 1
    )  # get_queryset returns a QuerySet; select_related applied to it pre-fetches editor in the same aggregate


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
    assert (
        count == 1
    )  # 1 foos find; bars is EmbeddedDocumentListField so no extra query, data is in the document


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
    assert (
        count == 1
    )  # 1 players aggregate with articles via select_related; first:3 pagination applied on pre-loaded list


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
    assert (
        count == 1
    )  # conflicting id+firstName filters produce an empty result; still only 1 query


# ---------------------------------------------------------------------------
# N+1 / query-count tests
# ---------------------------------------------------------------------------


def test_editors_with_company_no_pagination(fixtures):
    class Query(graphene.ObjectType):
        editors = MongoengineConnectionField(nodes.EditorNode)

    result, count = execute_count(
        graphene.Schema(query=Query),
        """
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
    """,
    )

    assert not result.errors
    names = [e["node"]["firstName"] for e in result.data["editors"]["edges"]]
    assert names == ["Penny", "Grant", "Dennis"]
    assert count == 1  # no pagination: 1 aggregate with $lookup for company; count query skipped


def test_articles_with_editor_and_company_no_pagination(fixtures):
    class Query(graphene.ObjectType):
        articles = MongoengineConnectionField(nodes.ArticleNode)

    result, count = execute_count(
        graphene.Schema(query=Query),
        """
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
    """,
    )

    assert not result.errors
    assert (
        count == 1
    )  # no pagination: 1 aggregate with nested $lookups for editor and editor→company; count query skipped


def test_articles_with_multiple_refs_no_pagination(fixtures):
    class Query(graphene.ObjectType):
        articles = MongoengineConnectionField(nodes.ArticleNode)

    result, count = execute_count(
        graphene.Schema(query=Query),
        """
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
    """,
    )

    assert not result.errors
    headlines = [e["node"]["headline"] for e in result.data["articles"]["edges"]]
    assert set(headlines) == {"Hello", "World", "Bye"}
    assert (
        count == 1
    )  # no pagination: 1 aggregate with $lookups for editor, editor→company, and reporter; count query skipped


def test_players_with_self_referential_no_pagination(fixtures):
    class Query(graphene.ObjectType):
        players = MongoengineConnectionField(nodes.PlayerNode)

    result, count = execute_count(
        graphene.Schema(query=Query),
        """
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
    """,
    )

    assert not result.errors
    magic = next(
        e["node"] for e in result.data["players"]["edges"] if e["node"]["firstName"] == "Magic"
    )
    assert magic["opponent"]["firstName"] == "Michael"
    assert (
        count == 1
    )  # no pagination: 1 aggregate with $lookup for opponent (self-referential join); count query skipped


def test_editors_paginated_first(fixtures):
    class Query(graphene.ObjectType):
        editors = MongoengineConnectionField(nodes.EditorNode)

    result, count = execute_count(
        graphene.Schema(query=Query),
        """
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
    """,
    )

    assert not result.errors
    names = [e["node"]["firstName"] for e in result.data["editors"]["edges"]]
    assert names == ["Penny", "Grant"]
    assert (
        count == 1
    )  # first:2 without pageInfo: count query skipped; 1 aggregate with $lookup for company


def test_editors_paginated_last(fixtures):
    class Query(graphene.ObjectType):
        editors = MongoengineConnectionField(nodes.EditorNode)

    result, count = execute_count(
        graphene.Schema(query=Query),
        """
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
    """,
    )

    assert not result.errors
    names = [e["node"]["firstName"] for e in result.data["editors"]["edges"]]
    assert names == ["Dennis"]
    assert count == 2  # last:1 triggers pagination: 1 count + 1 aggregate with $lookup for company


def test_editors_paginated_cursor_after(fixtures):
    class Query(graphene.ObjectType):
        editors = MongoengineConnectionField(nodes.EditorNode)

    schema = graphene.Schema(query=Query)
    cursor = offset_to_cursor(0)

    result, count = execute_count(
        schema,
        f"""
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
    """,
    )

    assert not result.errors
    names = [e["node"]["firstName"] for e in result.data["editors"]["edges"]]
    assert names == ["Grant", "Dennis"]
    assert (
        count == 1
    )  # first:2 with after cursor, no pageInfo: count query skipped; 1 aggregate with $lookup


def test_articles_paginated_first_with_editor(fixtures):
    class Query(graphene.ObjectType):
        articles = MongoengineConnectionField(nodes.ArticleNode)

    result, count = execute_count(
        graphene.Schema(query=Query),
        """
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
    """,
    )

    assert not result.errors
    assert len(result.data["articles"]["edges"]) == 2
    assert (
        count == 1
    )  # first:2 without pageInfo: count query skipped; 1 aggregate with $lookups for editor and editor→company


# ---------------------------------------------------------------------------
# MongoDB projection tests — verify only requested + required fields are fetched
# ---------------------------------------------------------------------------

from ..mongo_capture import captured_commands  # noqa: E402


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
    assert "fname" in projected  # first_name has db_field="fname"
    assert "last_name" not in projected
    assert "company" in projected  # company reference is projected (not all editor fields)


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
    assert "first_name" in reporter_projected  # queried reporter field
    assert "articles" in reporter_projected  # articles reference list is projected
    assert "email" not in reporter_projected  # unqueried reporter fields are excluded
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
    assert "first_name" in reporter_projected  # queried reporter field
    assert "generic_reference" in reporter_projected  # GenericReferenceField is projected
    assert "email" not in reporter_projected  # unqueried reporter fields are excluded
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
    assert "first_name" in reporter_projected  # queried reporter field
    assert (
        "generic_references" in reporter_projected
    )  # ListField(GenericReferenceField) is projected
    assert "email" not in reporter_projected  # unqueried reporter fields are excluded
    assert "awards" not in reporter_projected
    assert "articles" not in reporter_projected

    # select_related joins via $lookup in the same aggregate — no separate find
    assert len(cap.projected_fields_for("test_article")) == 0


def test_connection_field_resolver_returns_document_raises(fixtures):
    """A connection field resolver that returns a single document raises TypeError."""

    class Query(graphene.ObjectType):
        articles = MongoengineConnectionField(nodes.ArticleNode)

        def resolve_articles(self, info):
            return models.Article.objects.first()

    schema = graphene.Schema(query=Query)
    result = schema.execute("{ articles { edges { node { headline } } } }")
    assert result.errors
    assert "Article" in str(result.errors[0])
    assert "not supported" in str(result.errors[0])


# ---------------------------------------------------------------------------
# Enum field tests
# ---------------------------------------------------------------------------


def test_enum_field_query(fixtures):
    """ListField(EnumField) serialises enum values correctly in a relay query."""

    class Query(graphene.ObjectType):
        school_classes = MongoengineConnectionField(nodes.SchoolClassNode)

    schema = graphene.Schema(query=Query, auto_camelcase=True)
    result, count = execute_count(
        schema,
        "{ schoolClasses { edges { node { allowedGrades } } } }",
    )
    assert not result.errors, result.errors
    all_grades = [e["node"]["allowedGrades"] for e in result.data["schoolClasses"]["edges"]]
    assert ["A", "B"] in all_grades
    assert ["B"] in all_grades
    assert count == 1


def test_enum_field_filter(fixtures):
    """Filtering on a ListField(EnumField) by enum value returns only matching documents."""

    class Query(graphene.ObjectType):
        school_classes = MongoengineConnectionField(nodes.SchoolClassNode)

    schema = graphene.Schema(query=Query, auto_camelcase=True)
    # Enum values are passed without quotes in GraphQL (A not "A")
    result, count = execute_count(
        schema,
        "{ schoolClasses(allowedGrades: A) { edges { node { allowedGrades } } } }",
    )
    assert not result.errors, result.errors
    edges = result.data["schoolClasses"]["edges"]
    assert len(edges) == 1
    assert edges[0]["node"]["allowedGrades"] == ["A", "B"]
    assert count == 1


# ---------------------------------------------------------------------------
# Pagination edge cases
# ---------------------------------------------------------------------------


def test_empty_result_pageinfo(fixtures):
    """pageInfo on an empty result set has hasNextPage=False and hasPreviousPage=False."""

    class Query(graphene.ObjectType):
        articles = MongoengineConnectionField(nodes.ArticleNode)

    schema = graphene.Schema(query=Query, auto_camelcase=True)
    result, _ = execute_count(
        schema,
        '{ articles(headline: "__no_such_article__") { edges { node { headline } } pageInfo { hasNextPage hasPreviousPage } } }',
    )
    assert not result.errors, result.errors
    data = result.data["articles"]
    assert data["edges"] == []
    assert data["pageInfo"]["hasNextPage"] is False
    assert data["pageInfo"]["hasPreviousPage"] is False


# ---------------------------------------------------------------------------
# Meta option projection tests
# ---------------------------------------------------------------------------


def test_only_fields_restricts_mongodb_projection(fixtures):
    """only_fields on the Meta class limits which fields are fetched from MongoDB."""
    from graphene_mongo.synchronous.types import MongoengineObjectType
    from ..mongo_capture import captured_commands

    class EditorOnlyNameNode(MongoengineObjectType):
        class Meta:
            model = models.Editor
            interfaces = (Node,)
            only_fields = ("first_name",)

    class Query(graphene.ObjectType):
        editors = MongoengineConnectionField(EditorOnlyNameNode)

    schema = graphene.Schema(query=Query, auto_camelcase=True)
    with captured_commands() as cap:
        result = schema.execute("{ editors { edges { node { firstName } } } }")

    assert not result.errors, result.errors
    projected = cap.projected_fields()
    assert "fname" in projected
    assert "avatar" not in projected
    assert "last_name" not in projected


def test_exclude_fields_restricts_mongodb_projection(fixtures):
    """exclude_fields removes fields from the MongoDB projection."""
    from graphene_mongo.synchronous.types import MongoengineObjectType
    from ..mongo_capture import captured_commands

    class EditorNoAvatarNode(MongoengineObjectType):
        class Meta:
            model = models.Editor
            interfaces = (Node,)
            exclude_fields = ("avatar",)

    class Query(graphene.ObjectType):
        editors = MongoengineConnectionField(EditorNoAvatarNode)

    schema = graphene.Schema(query=Query, auto_camelcase=True)
    with captured_commands() as cap:
        result = schema.execute("{ editors { edges { node { firstName lastName } } } }")

    assert not result.errors, result.errors
    projected = cap.projected_fields()
    assert "fname" in projected
    assert "last_name" in projected
    assert "avatar" not in projected


def test_required_fields_always_projected(fixtures):
    """required_fields are included in the MongoDB projection even when not queried."""
    from graphene_mongo.synchronous.types import MongoengineObjectType
    from ..mongo_capture import captured_commands

    class EditorRequiredLastNameNode(MongoengineObjectType):
        class Meta:
            model = models.Editor
            interfaces = (Node,)
            required_fields = ("last_name",)

    class Query(graphene.ObjectType):
        editors = MongoengineConnectionField(EditorRequiredLastNameNode)

    schema = graphene.Schema(query=Query, auto_camelcase=True)
    with captured_commands() as cap:
        # Query only firstName — last_name is NOT in the GraphQL selection
        result = schema.execute("{ editors { edges { node { firstName } } } }")

    assert not result.errors, result.errors
    projected = cap.projected_fields()
    assert "last_name" in projected  # required_fields forces it into the projection
    assert "fname" in projected  # queried field is also projected


def test_geo_near_filter_arg_exists():
    """filter_fields {"loc": ["near"]} generates a loc__near arg with PointFieldInputType."""
    from graphene_mongo.synchronous.types import MongoengineObjectType
    from graphene_mongo.advanced_types import PointFieldInputType

    class ChildGeoNode(MongoengineObjectType):
        class Meta:
            model = models.Child
            interfaces = (Node,)
            filter_fields = {"loc": ["near"]}

    field = MongoengineConnectionField(ChildGeoNode)
    assert "loc__near" in field.args
    assert isinstance(field.args["loc__near"], graphene.Argument)
    assert field.args["loc__near"].type == PointFieldInputType


def test_geo_near_filter_query(fixtures):
    """loc__near filter returns only documents within the specified distance."""
    from graphene_mongo.synchronous.types import MongoengineObjectType

    class ChildGeoQueryNode(MongoengineObjectType):
        class Meta:
            model = models.Child
            interfaces = (Node,)
            filter_fields = {"loc": ["near"]}

    models.Child.ensure_indexes()

    class Query(graphene.ObjectType):
        children = MongoengineConnectionField(ChildGeoQueryNode)

    schema = graphene.Schema(query=Query, auto_camelcase=True)
    # child2 is at [10, 20]; child1 has no location.
    # Querying near [10, 20] should return child2 and exclude child1 (no loc).
    # auto_camelcase converts loc__near → loc_Near (double-underscore separator is preserved)
    result = schema.execute(
        """
        {
            children(loc_Near: {coordinates: [10.0, 20.0]}) {
                edges {
                    node {
                        bar
                    }
                }
            }
        }
        """
    )
    assert not result.errors, result.errors
    bars = [e["node"]["bar"] for e in result.data["children"]["edges"]]
    assert "bar" in bars
    assert "BAR" not in bars  # child1 has no loc, so it's excluded


def test_filter_fields_invalid_lookup_schema_arg_exists():
    """filter_fields with an unknown lookup builds the schema arg without error."""
    from graphene_mongo.synchronous.types import MongoengineObjectType

    class ArticleInvalidFilterNode(MongoengineObjectType):
        class Meta:
            model = models.Article
            interfaces = (Node,)
            filter_fields = {"headline": ["bad_op"]}

    field = MongoengineConnectionField(ArticleInvalidFilterNode)
    assert "headline__bad_op" in field.args


def test_filter_fields_invalid_lookup_raises_at_query_time(fixtures):
    """An unknown lookup in filter_fields is accepted by the schema but fails at query execution."""
    from graphene_mongo.synchronous.types import MongoengineObjectType

    class ArticleInvalidLookupNode(MongoengineObjectType):
        class Meta:
            model = models.Article
            interfaces = (Node,)
            filter_fields = {"headline": ["bad_op"]}

    class Query(graphene.ObjectType):
        articles = MongoengineConnectionField(ArticleInvalidLookupNode)

    schema = graphene.Schema(query=Query, auto_camelcase=True)
    result = schema.execute(
        '{ articles(headlineBadOp: "My Article") { edges { node { headline } } } }'
    )
    assert result.errors
