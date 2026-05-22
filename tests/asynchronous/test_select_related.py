"""
Query-count tests verifying that the select_related + skip-count optimizations
eliminate N+1 queries and unnecessary count calls.

Legend
------
- No pagination args (first/last/before/after absent):
    1 query  — single $aggregate with $lookup stages, count skipped
- Pagination args present:
    2 queries — 1 count + 1 $aggregate with $lookup stages
"""

import graphene
import pytest
from graphql_relay.connection.array_connection import offset_to_cursor
from mongoengine.context_managers import async_query_counter

from graphene_mongo import AsyncMongoengineConnectionField

from . import nodes


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _exec(schema, gql):
    """Execute a query and capture the DB query count."""
    async with async_query_counter() as q:
        result = await schema.execute_async(gql)
        count = await q.int()
    return result, count


# ---------------------------------------------------------------------------
# No-pagination tests: count must equal 1
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_editors_with_company_no_pagination(fixtures):
    """Single ReferenceField (editor → company): one aggregate, no count query."""

    class Query(graphene.ObjectType):
        editors = AsyncMongoengineConnectionField(nodes.EditorAsyncNode)

    result, count = await _exec(graphene.Schema(query=Query), """
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
    assert count == 1  # 1 aggregate($lookup company) — count skipped


@pytest.mark.asyncio
async def test_articles_with_editor_and_company_no_pagination(fixtures):
    """Two-level nesting (article → editor → company): still one aggregate."""

    class Query(graphene.ObjectType):
        articles = AsyncMongoengineConnectionField(nodes.ArticleAsyncNode)

    result, count = await _exec(graphene.Schema(query=Query), """
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
    assert count == 1  # 1 aggregate($lookup editor, $lookup editor.company)


@pytest.mark.asyncio
async def test_articles_with_multiple_refs_no_pagination(fixtures):
    """Two sibling ReferenceFields (editor → company, reporter) in one aggregate."""

    class Query(graphene.ObjectType):
        articles = AsyncMongoengineConnectionField(nodes.ArticleAsyncNode)

    result, count = await _exec(graphene.Schema(query=Query), """
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
    assert count == 1  # select_related("editor", "editor__company", "reporter")


@pytest.mark.asyncio
async def test_players_with_self_referential_no_pagination(fixtures):
    """Self-referential ReferenceField (player → opponent): one aggregate."""

    class Query(graphene.ObjectType):
        players = AsyncMongoengineConnectionField(nodes.PlayerAsyncNode)

    result, count = await _exec(graphene.Schema(query=Query), """
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
    assert count == 1  # select_related("opponent") — count skipped


# ---------------------------------------------------------------------------
# Pagination tests: count must equal 2 (1 count + 1 aggregate)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_editors_paginated_first(fixtures):
    """`first` triggers count + aggregate — still no per-editor company fetches."""

    class Query(graphene.ObjectType):
        editors = AsyncMongoengineConnectionField(nodes.EditorAsyncNode)

    result, count = await _exec(graphene.Schema(query=Query), """
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
    assert count == 2  # 1 count + 1 aggregate($lookup company)


@pytest.mark.asyncio
async def test_editors_paginated_last(fixtures):
    """`last` triggers count + aggregate."""

    class Query(graphene.ObjectType):
        editors = AsyncMongoengineConnectionField(nodes.EditorAsyncNode)

    result, count = await _exec(graphene.Schema(query=Query), """
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
    assert count == 2  # 1 count + 1 aggregate


@pytest.mark.asyncio
async def test_editors_paginated_cursor_after(fixtures):
    """`first` + `after` cursor triggers count + aggregate."""

    class Query(graphene.ObjectType):
        editors = AsyncMongoengineConnectionField(nodes.EditorAsyncNode)

    schema = graphene.Schema(query=Query)
    # cursor at position 0 → after it means from position 1 onward
    cursor = offset_to_cursor(0)

    result, count = await _exec(schema, f"""
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
    assert count == 2  # 1 count + 1 aggregate


@pytest.mark.asyncio
async def test_articles_paginated_first_with_editor(fixtures):
    """`first` on articles with nested editor ref: count + one aggregate."""

    class Query(graphene.ObjectType):
        articles = AsyncMongoengineConnectionField(nodes.ArticleAsyncNode)

    result, count = await _exec(graphene.Schema(query=Query), """
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
    assert count == 2  # 1 count + 1 aggregate($lookup editor, $lookup editor.company)