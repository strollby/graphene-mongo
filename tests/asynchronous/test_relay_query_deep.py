"""
Async stress tests for select_related with 10 levels of nested references.
Mirror of tests/synchronous/test_relay_query_deep.py using AsyncMongoengineObjectType.

Primary chain via .child:
  L1 → L2 → L3 → L4 → L5 → L6 → L7 → L8 → L9 → L10

Additional reference field variants exercised on the chain:

  Direct references (ListField / GenericReference on Document):
    L1.children         ListField(ReferenceField(L2))                     — relay connection
    L3.generic_item     GenericReferenceField → L4                        — union scalar
    L3.extra_refs       ListField(ReferenceField(L5))                     — relay connection
    L5.siblings         ListField(ReferenceField('self'))                 — self-referential relay connection
    L6.generic_item     GenericReferenceField → L7                        — union scalar
    L8.extras           ListField(ReferenceField(L10))                    — relay connection
    L8.generic_refs     ListField(GenericReferenceField([L9, L10]))       — list of union scalars  [scenario 1]

  Embedded document with references (DeepEmbedWithRef on L7):
    L7.embed            EmbeddedDocumentField(DeepEmbedWithRef)
                          └─ .ref_item     ReferenceField(L10)
                          └─ .generic_item GenericReferenceField([L9, L10])
                          └─ .list_refs    ListField(ReferenceField(L10)) — relay connection      [scenario 2]
                          └─ .nested       EmbeddedDocumentField(DeepNestedEmbed)
                                             └─ .ref_item  ReferenceField(L10)                   [scenario 3]
    L7.embeds           EmbeddedDocumentListField(DeepEmbedWithRef)  — plain List (no relay)
                          └─ [].ref_item     ReferenceField(L10)
                          └─ [].generic_item GenericReferenceField([L9, L10])
                          └─ [].list_refs    ListField(ReferenceField(L10))
                          └─ [].nested       EmbeddedDocumentField(DeepNestedEmbed)
                                               └─ .ref_item  ReferenceField(L10)

  Scenario coverage:
    1. ListField(GenericReferenceField) on a Document — L8.generic_refs
    2. ListField(ReferenceField) inside an EmbeddedDocument — DeepEmbedWithRef.list_refs
    3. Nested EmbeddedDocumentField within EmbeddedDocumentField with refs — DeepEmbedWithRef.nested

  The embedded-doc tests verify that get_select_related_paths recurses into
  EmbeddedDocumentField (and transitively into nested embedded docs), producing
  paths like "embed__ref_item", "embed__list_refs", "embed__nested__ref_item" so
  that all references are bulk-fetched in the same aggregation pipeline (no N+1).

All tests assert a single MongoDB query (no N+1) when using AsyncMongoengineConnectionField.
"""

import graphene
import pytest
from graphene.relay import Node

from . import nodes
from graphene_mongo.asynchronous.fields import AsyncMongoengineConnectionField
from .utils import execute_count

# ListField(ReferenceField) fields (extraRefs, siblings, extras, children)
# are relay connections because their target types have interfaces = (Node,).
DEEP_QUERY = """
{
    deepChain {
        edges {
            node {
                name
                child {
                    name
                    child {
                        name
                        genericItem { __typename }
                        extraRefs {
                            edges {
                                node {
                                    name
                                }
                            }
                        }
                        child {
                            name
                            child {
                                name
                                siblings {
                                    edges {
                                        node {
                                            name
                                        }
                                    }
                                }
                                child {
                                    name
                                    genericItem { __typename }
                                    child {
                                        name
                                        child {
                                            name
                                            extras {
                                                edges {
                                                    node {
                                                        name
                                                    }
                                                }
                                            }
                                            child {
                                                name
                                                child {
                                                    name
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
                children {
                    edges {
                        node {
                            name
                            child {
                                name
                            }
                        }
                    }
                }
            }
        }
    }
}
"""


@pytest.fixture(scope="module")
def deep_schema():
    class Query(graphene.ObjectType):
        node = Node.Field()
        deep_chain = AsyncMongoengineConnectionField(nodes.DeepL1AsyncNode)

    return graphene.Schema(query=Query, auto_camelcase=True)


async def test_deep_select_related_data_correctness(fixtures, deep_schema):
    """All 10 levels resolve to the correct names."""
    result, _ = await execute_count(deep_schema, DEEP_QUERY)
    assert not result.errors, result.errors

    node = result.data["deepChain"]["edges"][0]["node"]
    assert node["name"] == "L1"

    l2 = node["child"]
    assert l2["name"] == "L2-A"

    l3 = l2["child"]
    assert l3["name"] == "L3"
    assert l3["genericItem"]["__typename"] == "DeepL4AsyncNode"
    extra_ref_nodes = [e["node"] for e in l3["extraRefs"]["edges"]]
    assert {r["name"] for r in extra_ref_nodes} == {"L5-A", "L5-B"}

    l4 = l3["child"]
    assert l4["name"] == "L4"

    l5 = l4["child"]
    assert l5["name"] == "L5-A"
    sibling_nodes = [e["node"] for e in l5["siblings"]["edges"]]
    assert sibling_nodes == [{"name": "L5-B"}]

    l6 = l5["child"]
    assert l6["name"] == "L6"
    assert l6["genericItem"]["__typename"] == "DeepL7AsyncNode"

    l7 = l6["child"]
    assert l7["name"] == "L7"

    l8 = l7["child"]
    assert l8["name"] == "L8"
    extra_nodes = [e["node"] for e in l8["extras"]["edges"]]
    assert {e["name"] for e in extra_nodes} == {"L10-B", "L10-C"}

    l9 = l8["child"]
    assert l9["name"] == "L9"

    l10 = l9["child"]
    assert l10["name"] == "L10-A"

    children_nodes = [e["node"] for e in node["children"]["edges"]]
    assert len(children_nodes) == 2
    assert {c["name"] for c in children_nodes} == {"L2-A", "L2-B"}
    for c in children_nodes:
        assert c["child"]["name"] == "L3"


async def test_deep_select_related_single_query(fixtures, deep_schema):
    """The entire 10-level graph is resolved in a single MongoDB aggregate."""
    result, count = await execute_count(deep_schema, DEEP_QUERY)
    assert not result.errors, result.errors
    assert count == 1, f"Expected 1 query, got {count} — N+1 detected"


async def test_deep_list_of_references(fixtures, deep_schema):
    """ListField(ReferenceField) at L1.children and L3.extraRefs resolve all items."""
    query = """
    {
        deepChain {
            edges {
                node {
                    name
                    children {
                        edges {
                            node {
                                name
                                child { name }
                            }
                        }
                    }
                    child {
                        child {
                            extraRefs {
                                edges {
                                    node {
                                        name
                                        child { name }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    """
    result, count = await execute_count(deep_schema, query)
    assert not result.errors, result.errors
    node = result.data["deepChain"]["edges"][0]["node"]

    children_nodes = [e["node"] for e in node["children"]["edges"]]
    assert len(children_nodes) == 2
    assert {c["name"] for c in children_nodes} == {"L2-A", "L2-B"}

    extra_ref_nodes = [e["node"] for e in node["child"]["child"]["extraRefs"]["edges"]]
    assert len(extra_ref_nodes) == 2
    assert {r["name"] for r in extra_ref_nodes} == {"L5-A", "L5-B"}
    for r in extra_ref_nodes:
        assert r["child"]["name"] == "L6"

    assert count == 1


async def test_deep_generic_references(fixtures, deep_schema):
    """GenericReferenceFields at L3 and L6 resolve to the correct concrete types."""
    query = """
    {
        deepChain {
            edges {
                node {
                    child {
                        child {
                            genericItem { __typename }
                            child {
                                child {
                                    child {
                                        genericItem { __typename }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    """
    result, count = await execute_count(deep_schema, query)
    assert not result.errors, result.errors
    l2 = result.data["deepChain"]["edges"][0]["node"]["child"]
    l3 = l2["child"]
    assert l3["genericItem"]["__typename"] == "DeepL4AsyncNode"
    l6 = l3["child"]["child"]["child"]
    assert l6["genericItem"]["__typename"] == "DeepL7AsyncNode"
    assert count == 1


async def test_deep_self_referential_list(fixtures, deep_schema):
    """Self-referential ListField(ReferenceField('self')) at L5 resolves correctly."""
    query = """
    {
        deepChain {
            edges {
                node {
                    child {
                        child {
                            child {
                                child {
                                    name
                                    siblings {
                                        edges {
                                            node {
                                                name
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    """
    result, count = await execute_count(deep_schema, query)
    assert not result.errors, result.errors
    l5 = result.data["deepChain"]["edges"][0]["node"]["child"]["child"]["child"]["child"]
    assert l5["name"] == "L5-A"
    sibling_nodes = [e["node"] for e in l5["siblings"]["edges"]]
    assert sibling_nodes == [{"name": "L5-B"}]
    assert count == 1


async def test_deep_list_at_depth_8(fixtures, deep_schema):
    """ListField(ReferenceField) at L8.extras (pointing to L10) resolves all items."""
    query = """
    {
        deepChain {
            edges {
                node {
                    child { child { child { child { child { child { child {
                        name
                        extras {
                            edges {
                                node {
                                    name
                                }
                            }
                        }
                        child {
                            name
                            child { name }
                        }
                    } } } } } } }
                }
            }
        }
    }
    """
    result, count = await execute_count(deep_schema, query)
    assert not result.errors, result.errors
    l8 = result.data["deepChain"]["edges"][0]["node"]["child"]["child"]["child"]["child"]["child"][
        "child"
    ]["child"]
    assert l8["name"] == "L8"
    extra_nodes = [e["node"] for e in l8["extras"]["edges"]]
    assert {e["name"] for e in extra_nodes} == {"L10-B", "L10-C"}
    assert l8["child"]["name"] == "L9"
    assert l8["child"]["child"]["name"] == "L10-A"
    assert count == 1


async def test_deep_embedded_doc_with_refs(fixtures, deep_schema):
    """EmbeddedDocumentField containing ReferenceField and GenericReferenceField resolves
    via select_related — both refItem and genericItem are resolved in 1 query."""
    query = """
    {
        deepChain {
            edges {
                node {
                    child { child { child { child { child { child {
                        name
                        embed {
                            label
                            refItem { name }
                            genericItem {
                                __typename
                                ... on DeepL9AsyncNode { name }
                                ... on DeepL10AsyncNode { name }
                            }
                        }
                    } } } } } }
                }
            }
        }
    }
    """
    result, count = await execute_count(deep_schema, query)
    assert not result.errors, result.errors
    l7 = result.data["deepChain"]["edges"][0]["node"]["child"]["child"]["child"]["child"]["child"][
        "child"
    ]
    assert l7["name"] == "L7"
    embed = l7["embed"]
    assert embed["label"] == "embed-single"
    assert embed["refItem"]["name"] == "L10-A"
    assert embed["genericItem"]["__typename"] == "DeepL9AsyncNode"
    assert embed["genericItem"]["name"] == "L9"
    assert count == 1


async def test_deep_embedded_doc_list_with_refs(fixtures, deep_schema):
    """EmbeddedDocumentListField containing ReferenceField and GenericReferenceField
    resolves all items and their references via select_related in 1 query."""
    query = """
    {
        deepChain {
            edges {
                node {
                    child { child { child { child { child { child {
                        name
                        embeds {
                            label
                            refItem { name }
                            genericItem {
                                __typename
                                ... on DeepL9AsyncNode { name }
                                ... on DeepL10AsyncNode { name }
                            }
                        }
                    } } } } } }
                }
            }
        }
    }
    """
    result, count = await execute_count(deep_schema, query)
    assert not result.errors, result.errors
    l7 = result.data["deepChain"]["edges"][0]["node"]["child"]["child"]["child"]["child"]["child"][
        "child"
    ]
    assert l7["name"] == "L7"
    embeds = l7["embeds"]
    assert len(embeds) == 2
    by_label = {e["label"]: e for e in embeds}
    assert by_label["embed-list-0"]["refItem"]["name"] == "L10-B"
    assert by_label["embed-list-0"]["genericItem"]["__typename"] == "DeepL10AsyncNode"
    assert by_label["embed-list-0"]["genericItem"]["name"] == "L10-C"
    assert by_label["embed-list-1"]["refItem"]["name"] == "L10-C"
    assert by_label["embed-list-1"]["genericItem"]["__typename"] == "DeepL9AsyncNode"
    assert by_label["embed-list-1"]["genericItem"]["name"] == "L9"
    assert count == 1


async def test_deep_list_of_generic_references(fixtures, deep_schema):
    """ListField(GenericReferenceField) at L8.genericRefs resolves all items via select_related."""
    query = """
    {
        deepChain {
            edges {
                node {
                    child { child { child { child { child { child { child {
                        name
                        genericRefs {
                            __typename
                            ... on DeepL9AsyncNode { name }
                            ... on DeepL10AsyncNode { name }
                        }
                    } } } } } } }
                }
            }
        }
    }
    """
    result, count = await execute_count(deep_schema, query)
    assert not result.errors, result.errors
    l8 = result.data["deepChain"]["edges"][0]["node"]["child"]["child"]["child"]["child"]["child"][
        "child"
    ]["child"]
    assert l8["name"] == "L8"
    generic_refs = l8["genericRefs"]
    assert len(generic_refs) == 2
    by_type = {item["__typename"]: item for item in generic_refs}
    assert by_type["DeepL9AsyncNode"]["name"] == "L9"
    assert by_type["DeepL10AsyncNode"]["name"] == "L10-B"
    assert count == 1


async def test_deep_embed_list_refs(fixtures, deep_schema):
    """ListField(ReferenceField) inside EmbeddedDocumentField resolves via select_related in 1 query."""
    query = """
    {
        deepChain {
            edges {
                node {
                    child { child { child { child { child { child {
                        name
                        embed {
                            label
                            listRefs {
                                edges {
                                    node {
                                        name
                                    }
                                }
                            }
                        }
                    } } } } } }
                }
            }
        }
    }
    """
    result, count = await execute_count(deep_schema, query)
    assert not result.errors, result.errors
    l7 = result.data["deepChain"]["edges"][0]["node"]["child"]["child"]["child"]["child"]["child"][
        "child"
    ]
    assert l7["name"] == "L7"
    embed = l7["embed"]
    assert embed["label"] == "embed-single"
    list_ref_names = {e["node"]["name"] for e in embed["listRefs"]["edges"]}
    assert list_ref_names == {"L10-B", "L10-C"}
    assert count == 1


async def test_deep_nested_embed_ref(fixtures, deep_schema):
    """Nested EmbeddedDocumentField within EmbeddedDocumentField: embed.nested.refItem
    is resolved via select_related path 'embed__nested__ref_item' in 1 query."""
    query = """
    {
        deepChain {
            edges {
                node {
                    child { child { child { child { child { child {
                        name
                        embed {
                            label
                            nested {
                                refItem { name }
                            }
                        }
                    } } } } } }
                }
            }
        }
    }
    """
    result, count = await execute_count(deep_schema, query)
    assert not result.errors, result.errors
    l7 = result.data["deepChain"]["edges"][0]["node"]["child"]["child"]["child"]["child"]["child"][
        "child"
    ]
    assert l7["name"] == "L7"
    embed = l7["embed"]
    assert embed["label"] == "embed-single"
    assert embed["nested"]["refItem"]["name"] == "L10-A"
    assert count == 1
