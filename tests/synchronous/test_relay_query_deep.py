"""
Stress tests for select_related with 10 levels of nested references.

Chain via .child:
  L1 → L2 → L3 → L4 → L5 → L6 → L7 → L8 → L9 → L10

Additional reference types exercised:
  L1.children         ListField(ReferenceField(L2))
  L3.generic_item     GenericReferenceField → L4
  L3.extra_refs       ListField(ReferenceField(L5))
  L5.siblings         ListField(ReferenceField(L5)) — self-referential
  L6.generic_item     GenericReferenceField → L7
  L8.extras           ListField(ReferenceField(L10))

All tests assert a single MongoDB query (no N+1) when using MongoengineConnectionField.
"""

import graphene
import pytest
from graphene.relay import Node

from . import nodes
from graphene_mongo.synchronous.fields import MongoengineConnectionField
from .utils import execute_count

# 10-level deep connection query — traverses the full L1→...→L10 child chain
# and exercises ListField, GenericReferenceField, and self-referential refs.
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
        deep_chain = MongoengineConnectionField(nodes.DeepL1Node)

    return graphene.Schema(query=Query, auto_camelcase=True)


def test_deep_select_related_data_correctness(fixtures, deep_schema):
    """All 10 levels resolve to the correct names."""
    result, _ = execute_count(deep_schema, DEEP_QUERY)
    assert not result.errors, result.errors

    node = result.data["deepChain"]["edges"][0]["node"]
    assert node["name"] == "L1"

    l2 = node["child"]
    assert l2["name"] == "L2-A"

    l3 = l2["child"]
    assert l3["name"] == "L3"
    assert l3["genericItem"]["__typename"] == "DeepL4Node"
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
    assert l6["genericItem"]["__typename"] == "DeepL7Node"

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

    # children list at L1 → two L2 docs
    children_nodes = [e["node"] for e in node["children"]["edges"]]
    assert len(children_nodes) == 2
    assert {c["name"] for c in children_nodes} == {"L2-A", "L2-B"}
    for c in children_nodes:
        assert c["child"]["name"] == "L3"


def test_deep_select_related_single_query(fixtures, deep_schema):
    """The entire 10-level graph is resolved in a single MongoDB aggregate."""
    result, count = execute_count(deep_schema, DEEP_QUERY)
    assert not result.errors, result.errors
    assert count == 1, f"Expected 1 query, got {count} — N+1 detected"


def test_deep_list_of_references(fixtures, deep_schema):
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
    result, count = execute_count(deep_schema, query)
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


def test_deep_generic_references(fixtures, deep_schema):
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
    result, count = execute_count(deep_schema, query)
    assert not result.errors, result.errors
    l2 = result.data["deepChain"]["edges"][0]["node"]["child"]
    l3 = l2["child"]
    assert l3["genericItem"]["__typename"] == "DeepL4Node"
    l6 = l3["child"]["child"]["child"]
    assert l6["genericItem"]["__typename"] == "DeepL7Node"
    assert count == 1


def test_deep_self_referential_list(fixtures, deep_schema):
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
    result, count = execute_count(deep_schema, query)
    assert not result.errors, result.errors
    l5 = result.data["deepChain"]["edges"][0]["node"]["child"]["child"]["child"]["child"]
    assert l5["name"] == "L5-A"
    sibling_nodes = [e["node"] for e in l5["siblings"]["edges"]]
    assert sibling_nodes == [{"name": "L5-B"}]
    assert count == 1


def test_deep_list_at_depth_8(fixtures, deep_schema):
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
    result, count = execute_count(deep_schema, query)
    assert not result.errors, result.errors
    l8 = result.data["deepChain"]["edges"][0]["node"]["child"]["child"]["child"]["child"]["child"]["child"]["child"]
    assert l8["name"] == "L8"
    extra_nodes = [e["node"] for e in l8["extras"]["edges"]]
    assert {e["name"] for e in extra_nodes} == {"L10-B", "L10-C"}
    assert l8["child"]["name"] == "L9"
    assert l8["child"]["child"]["name"] == "L10-A"
    assert count == 1