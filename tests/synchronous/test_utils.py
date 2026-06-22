import graphene

from .. import types
from ..models import Article, Child, Player, Reporter
from graphene_mongo.base.utils import (
    get_model_fields,
    get_query_fields,
    get_select_related_paths,
    is_valid_mongoengine_model,
)


def test_get_model_fields_no_duplication():
    reporter_fields = get_model_fields(Reporter)
    reporter_name_set = set(reporter_fields)
    assert len(reporter_fields) == len(reporter_name_set)


def test_get_model_fields_excluding():
    reporter_fields = get_model_fields(Reporter, excluding=["first_name", "last_name"])
    reporter_name_set = set(reporter_fields)
    assert all(
        field in reporter_name_set
        for field in [
            "id",
            "email",
            "articles",
            "embedded_articles",
            "embedded_list_articles",
            "awards",
        ]
    )


def test_get_model_relation_fields():
    article_fields = get_model_fields(Article)
    assert all(field in set(article_fields) for field in ["editor", "reporter"])


def test_get_base_model_fields():
    child_fields = get_model_fields(Child)
    assert all(field in set(child_fields) for field in ["bar", "baz"])


def test_is_valid_mongoengine_mode():
    assert is_valid_mongoengine_model(Reporter)


def test_get_query_fields():
    # Grab ResolveInfo objects from resolvers and set as nonlocal variables outside
    # Can't assert within resolvers, as the resolvers may not be run if there is an exception
    class Query(graphene.ObjectType):
        child = graphene.Field(types.ChildType)
        children = graphene.List(types.ChildUnionType)

        def resolve_child(self, info, *args, **kwargs):
            test_get_query_fields.child_info = info

        def resolve_children(self, info, *args, **kwargs):
            test_get_query_fields.children_info = info

    query = """
        query Query {
            child {
                bar
                ...testFragment
            }
            children {
                ... on ChildType{
                    baz
                    ...testFragment
                }
                ... on AnotherChildType {
                    qux
                }
            }
        }

        fragment testFragment on ChildType {
            loc {
                type
                coordinates
            }
        }
    """

    schema = graphene.Schema(query=Query)
    schema.execute(query)

    assert get_query_fields(test_get_query_fields.child_info) == {
        "bar": {},
        "loc": {
            "type": {},
            "coordinates": {},
        },
    }

    assert get_query_fields(test_get_query_fields.children_info) == {
        "ChildType": {
            "baz": {},
            "loc": {
                "type": {},
                "coordinates": {},
            },
        },
        "AnotherChildType": {
            "qux": {},
        },
    }


def test_get_select_related_paths_top_level():
    """Returns a path for each top-level reference field that was queried."""
    queried = {"editor": {"firstName": {}}, "headline": {}}
    paths = get_select_related_paths(Article, queried)
    assert paths == ["editor"]


def test_get_select_related_paths_nested():
    """Recursively returns nested reference paths using __ notation."""
    # Editor.company is a ReferenceField(Publisher)
    queried = {"editor": {"firstName": {}, "company": {"name": {}}}}
    paths = get_select_related_paths(Article, queried)
    assert "editor" in paths
    assert "editor__company" in paths


def test_get_select_related_paths_no_refs():
    """Returns an empty list when no reference fields are queried."""
    queried = {"headline": {}, "pubDate": {}}
    paths = get_select_related_paths(Article, queried)
    assert paths == []


def test_get_select_related_paths_unknown_field_ignored():
    """Unknown GraphQL fields (not in model._fields) are silently skipped."""
    queried = {"nonExistentField": {"sub": {}}, "headline": {}}
    paths = get_select_related_paths(Article, queried)
    assert paths == []


def test_get_select_related_paths_reporter_articles():
    """ListField(ReferenceField) is also included — articles is a list of Article refs."""
    queried = {"articles": {"headline": {}}}
    paths = get_select_related_paths(Reporter, queried)
    assert "articles" in paths


def test_get_select_related_paths_self_referential_terminates():
    """Self-referential ListField(ReferenceField('self')) terminates at query depth."""
    # Player.players = ListField(ReferenceField('Player')) — a cycle in the schema.
    # Termination is guaranteed by the finite depth of the queried_fields dict (from
    # the parsed GraphQL query), not by any explicit cycle-breaking in the function.
    queried = {
        "players": {
            "firstName": {},
            "players": {
                "firstName": {},
            },
        }
    }
    paths = get_select_related_paths(Player, queried)
    assert "players" in paths
    assert "players__players" in paths


def test_get_select_related_paths_relay_connection_unwrapped():
    """Relay edges→node wrapper around sub-fields is unwrapped so nested paths are found."""
    # When Player.players is rendered as a Relay connection, sub-fields arrive
    # wrapped in edges→node. The function should unwrap and still find nested refs.
    queried = {
        "players": {
            "edges": {
                "node": {
                    "firstName": {},
                    "opponent": {"firstName": {}},
                }
            }
        }
    }
    paths = get_select_related_paths(Player, queried)
    assert "players" in paths
    assert "players__opponent" in paths
