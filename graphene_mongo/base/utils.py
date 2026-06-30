import enum
import inspect
from typing import Callable, Optional

from graphene import Node
from graphene.utils.str_converters import to_snake_case
from graphene.utils.trim_docstring import trim_docstring
from graphql import (
    BooleanValueNode,
    FieldNode,
    GraphQLIncludeDirective,
    GraphQLSkipDirective,
    VariableNode,
)
from graphql_relay.connection.array_connection import offset_to_cursor
import mongoengine
from mongoengine.base.common import _DocumentRegistry


class ExecutorEnum(enum.Enum):
    """Enumeration distinguishing synchronous from asynchronous field execution.

    Used throughout the library to select the correct resolver variant and
    QuerySet manager (model.objects vs model.aobjects).
    """

    ASYNC = enum.auto()
    SYNC = enum.auto()


def get_document(model):
    """Look up a MongoEngine document class by name or class reference.

    Args:
        model (str | type): Either a MongoEngine document class or its class name string.

    Returns:
        type: The MongoEngine document class retrieved from the global document registry.
    """
    model_name = model
    if not isinstance(model, str):
        model_name = model.__name__

    return _DocumentRegistry.get(model_name)


def get_model_fields(model, excluding=None):
    """Return all MongoEngine fields on *model* in alphabetical order.

    Args:
        model: A MongoEngine Document or EmbeddedDocument class.
        excluding (list[str] | None): Field names to omit from the result.

    Returns:
        dict[str, mongoengine.BaseField]: Alphabetically sorted mapping of
        field name → MongoEngine field instance.
    """
    excluding = excluding or []
    attributes = dict()
    for attr_name, attr in model._fields.items():
        if attr_name in excluding:
            continue
        attributes[attr_name] = attr
    return dict(sorted(attributes.items()))


def get_model_reference_fields(model, excluding=None):
    """Return only the ReferenceField fields on *model*.

    Used by _hydrate_args
    to identify which query arguments represent references that need to be decoded
    from Relay global IDs to MongoEngine document stubs.

    Args:
        model: A MongoEngine Document or EmbeddedDocument class.
        excluding (list[str] | None): Field names to omit from the result.

    Returns:
        dict[str, mongoengine.ReferenceField]: Mapping of field name → ReferenceField
        for all reference fields on the model.
    """
    excluding = excluding or []
    attributes = dict()
    for attr_name, attr in model._fields.items():
        if attr_name in excluding or not isinstance(
            attr,
            mongoengine.fields.ReferenceField,
        ):
            continue
        attributes[attr_name] = attr
    return attributes


def is_valid_mongoengine_model(model):
    """Return True if *model* is a MongoEngine Document or EmbeddedDocument class.

    Args:
        model: Any Python object to check.

    Returns:
        bool: True when *model* is a class that subclasses Document or
        EmbeddedDocument; False otherwise.
    """
    return inspect.isclass(model) and (
        issubclass(model, mongoengine.Document) or issubclass(model, mongoengine.EmbeddedDocument)
    )


def get_field_description(field, registry=None):
    """
    Common metadata includes verbose_name and help_text.

    http://docs.mongoengine.org/apireference.html#fields
    """
    parts = []
    if hasattr(field, "document_type"):
        doc = trim_docstring(field.document_type.__doc__)
        if doc:
            parts.append(doc)
    if hasattr(field, "verbose_name"):
        parts.append(field.verbose_name.title())
    if hasattr(field, "help_text"):
        parts.append(field.help_text)
    if hasattr(field, "description"):
        parts.append(field.description)
    if field.db_field != field.name:
        name_format = "(%s)" if parts else "%s"
        parts.append(name_format % field.db_field)

    return "\n".join(parts)


def get_field_is_required(field, registry=None):
    """
    A field is said to be required in gql only if
    field.required = True and field.null = False
    """
    return field.required and not field.null


def get_node_from_global_id(node, info, global_id):
    """Resolve a Relay global ID to the corresponding MongoEngine document.

    Walks the node's interface list looking for a Node interface and delegates
    to its get_node_from_global_id implementation.  Falls back to
    Node.get_node_from_global_id if the node has no _meta.interfaces.

    Args:
        node: A graphene ObjectType class implementing the Relay Node interface.
        info: GraphQL resolve info object.
        global_id (str): The Relay-encoded global ID (e.g. "QXJ0aWNsZTox").

    Returns:
        Document | None: The fetched MongoEngine document, or None if not found.
    """
    try:
        for interface in node._meta.interfaces:
            if issubclass(interface, Node):
                return interface.get_node_from_global_id(info, global_id)
    except AttributeError:
        return Node.get_node_from_global_id(info, global_id)


def include_field_by_directives(node, variables):
    """
    Evaluates the graphql directives to determine if the queried field is to be included

    Handles Directives
    @skip
    @include

    """
    directives = node.get("directives") if isinstance(node, dict) else node.directives
    if not directives:
        return True

    directive_results = []
    for directive in directives:
        argument_results = []
        for argument in directive.arguments:
            if isinstance(argument.value, BooleanValueNode):
                argument_results.append(argument.value.value)
            elif isinstance(argument.value, VariableNode):
                argument_results.append(variables.get(argument.value.name.value))

        directive_name = directive.name.value
        if directive_name == GraphQLIncludeDirective.name:
            directive_results.append(True if any(argument_results) else False)
        elif directive_name == GraphQLSkipDirective.name:
            directive_results.append(False if all(argument_results) else True)

    return all(directive_results) if len(directive_results) > 0 else True


def collect_query_fields(node, fragments, variables):
    """Recursively collects fields from the AST

    Args:
        node (dict): A node in the AST
        fragments (dict): Fragment definitions
        variables (dict): User defined variables & values

    Returns:
        A dict mapping each field found, along with their sub fields.
        {
            'name': {},
            'image': {
                        'id': {},
                        'name': {},
                        'description': {}
                    },
            'slug': {}
        }
    """

    field = {}
    selection_set = node.get("selection_set") if isinstance(node, dict) else node.selection_set
    if selection_set:
        for leaf in selection_set.selections:
            if leaf.kind == "field":
                if include_field_by_directives(leaf, variables):
                    field.update(
                        {leaf.name.value: collect_query_fields(leaf, fragments, variables)}
                    )
            elif leaf.kind == "fragment_spread":
                field.update(collect_query_fields(fragments[leaf.name.value], fragments, variables))
            elif leaf.kind == "inline_fragment":
                field.update(
                    {
                        leaf.type_condition.name.value: collect_query_fields(
                            leaf, fragments, variables
                        )
                    }
                )

    return field


def get_query_fields(info):
    """A convenience function to call collect_query_fields with info

    Args:
        info (ResolveInfo)

    Returns:
        dict: Returned from collect_query_fields
    """

    fragments = {}
    node = ast_to_dict(info.field_nodes[0])
    variables = info.variable_values

    for name, value in info.fragments.items():
        fragments[name] = ast_to_dict(value)

    query = collect_query_fields(node, fragments, variables)
    if "edges" in query:
        return query["edges"]["node"]
    return query


def get_select_related_paths(model, queried_fields, prefix=""):
    """Recursively build select_related paths for queried reference fields.

    Returns __-separated paths (e.g. ["editor", "editor__company"])
    suitable for QuerySet.select_related(*paths).
    """
    paths = []
    if not queried_fields or not hasattr(queried_fields, "items"):
        return paths
    for field_name, sub_fields in queried_fields.items():
        snake = to_snake_case(field_name)
        if snake not in model._fields:
            continue
        mongo_field = model._fields[snake]
        inner = mongo_field.field if isinstance(mongo_field, mongoengine.ListField) else mongo_field
        if isinstance(inner, (mongoengine.ReferenceField, mongoengine.GenericReferenceField)):
            path = f"{prefix}__{snake}" if prefix else snake
            paths.append(path)
            if sub_fields and hasattr(inner, "document_type"):
                # Unwrap Relay edges→node wrapper so nested fields (e.g. beforeChild→parent)
                # are visible to the recursion even when the sub-field is a connection.
                effective = sub_fields.get("edges", {}).get("node") or sub_fields
                paths += get_select_related_paths(inner.document_type, effective, prefix=path)
        elif isinstance(inner, mongoengine.EmbeddedDocumentField):
            # Embedded docs are stored inline — no select_related path needed for the
            # embedded doc itself, but any ReferenceField inside it does need one.
            # Path prefix grows (e.g. "embed") so nested refs become "embed__ref_item".
            if sub_fields and hasattr(inner, "document_type"):
                path = f"{prefix}__{snake}" if prefix else snake
                paths += get_select_related_paths(inner.document_type, sub_fields, prefix=path)
    return paths


def get_queried_union_types(info, valid_gql_types):
    """A convenience function to get queried union types with its fields

    Args:
        info (ResolveInfo)
        valid_gql_types (dict_keys)

    Returns:
        dict[union_type_name, queried_fields(dict)]
    """

    def collect_query_fields_for_union(node, fragments, variables):
        """
        Similar to collect_query_fields(...)

        fragment_spread - logic is different for union
        """

        field = {}
        selection_set = node.get("selection_set") if isinstance(node, dict) else node.selection_set
        if selection_set:
            for leaf in selection_set.selections:
                if leaf.kind == "field":
                    if include_field_by_directives(leaf, variables):
                        field.update(
                            {leaf.name.value: collect_query_fields(leaf, fragments, variables)}
                        )
                elif leaf.kind == "fragment_spread":  # This is different
                    fragment = fragments[leaf.name.value]
                    field.update(
                        {
                            fragment.type_condition.name.value: collect_query_fields(
                                fragment, fragments, variables
                            )
                        }
                    )
                elif leaf.kind == "inline_fragment":
                    field.update(
                        {
                            leaf.type_condition.name.value: collect_query_fields(
                                leaf, fragments, variables
                            )
                        }
                    )

        return field

    fragments = {}
    node = ast_to_dict(info.field_nodes[0])
    variables = info.variable_values

    for name, value in info.fragments.items():
        fragments[name] = ast_to_dict(value)

    fragments_queries: dict[str, dict] = {}

    selection_set = node.get("selection_set") if isinstance(node, dict) else node.selection_set
    if selection_set:
        for leaf in selection_set.selections:
            if leaf.kind == "fragment_spread":
                fragment_name = fragments[leaf.name.value].type_condition.name.value
                sub_query_fields = collect_query_fields_for_union(
                    fragments[leaf.name.value], fragments, variables
                )
                if fragment_name not in valid_gql_types:
                    # This is done to avoid UnionFragments coming in fragments_queries as
                    # we actually need its children types and not the UnionFragments itself
                    fragments_queries.update(sub_query_fields)
                    fragments_queries.pop(
                        "__typename", None
                    )  # cannot resolve __typename for a union type
                else:
                    fragments_queries[fragment_name] = sub_query_fields
            elif leaf.kind == "inline_fragment":
                fragment_name = leaf.type_condition.name.value
                fragments_queries[fragment_name] = collect_query_fields_for_union(
                    leaf, fragments, variables
                )

    return fragments_queries


def has_page_info(info):
    """A convenience function to call collect_query_fields with info
    for retrieving if page_info details are required

    Args:
        info (ResolveInfo)

    Returns:
        bool: True if it received pageinfo
    """

    fragments = {}
    if not info:
        return True  # Returning True if invalid info is provided
    node = ast_to_dict(info.field_nodes[0])
    variables = info.variable_values

    for name, value in info.fragments.items():
        fragments[name] = ast_to_dict(value)

    query = collect_query_fields(node, fragments, variables)
    return next((True for x in query.keys() if x.lower() == "pageinfo"), False)


def ast_to_dict(node, include_loc=False):
    """Recursively convert a GraphQL AST node to a plain Python dict.

    Only FieldNode instances are expanded; all other node types (scalars,
    lists, etc.) are returned as-is.  This simplified representation is used by
    collect_query_fields and friends to traverse the selection set without
    importing every AST node type.

    Args:
        node: A GraphQL AST node or any Python value.
        include_loc (bool): When True, a "loc" key with start/end
            positions is included for each FieldNode.

    Returns:
        dict | list | Any: The converted representation.
    """
    if isinstance(node, FieldNode):
        d = {"kind": node.__class__.__name__}
        if hasattr(node, "keys"):
            for field in node.keys:
                d[field] = ast_to_dict(getattr(node, field), include_loc)

        if include_loc and hasattr(node, "loc") and node.loc:
            d["loc"] = {"start": node.loc.start, "end": node.loc.end}

        return d

    elif isinstance(node, list):
        return [ast_to_dict(item, include_loc) for item in node]

    return node


def find_skip_and_limit(first, last, after, before, count=None):
    """Compute MongoDB skip and limit values from Relay cursor-pagination args.

    Implements the Relay cursor connection spec
    (https://relay.dev/graphql/connections.htm) for first / last /
    before / after pagination.

    Args:
        first (int | None): Return the first N edges after *after*.
        last (int | None): Return the last N edges before *before*.
        after (int | None): 0-based offset cursor; edges after this position.
        before (int | None): 0-based offset cursor; edges before this position.
        count (int | None): Total number of matching documents.  **Required** when
            *last* is not None; a ValueError is raised otherwise.

    Returns:
        tuple[int, int | None]: (skip, limit) where skip is the number of
        documents to skip and limit is the page size (None means no limit).

    Raises:
        ValueError: When *last* is provided but *count* is None.
    """
    skip = 0
    limit = None

    if last is not None and count is None:
        raise ValueError("Count Missing")

    if first is not None and after is not None:
        skip = after + 1
        limit = first
    elif first is not None and before is not None:
        if first >= before:
            limit = before - 1
        else:
            limit = first
    elif first is not None:
        skip = 0
        limit = first
    elif last is not None and before is not None:
        if last >= before:
            limit = before
        else:
            limit = last
            skip = before - last
    elif last is not None and after is not None:
        skip = after + 1
        if last + after < count:
            limit = last
        else:
            limit = count - after - 1
    elif last is not None:
        skip = count - last
        limit = last
    elif after is not None:
        skip = after + 1
    elif before is not None:
        limit = before

    return skip, limit


def connection_from_iterables(
    edges,
    start_offset,
    has_previous_page,
    has_next_page,
    connection_type,
    edge_type,
    pageinfo_type,
):
    """Build a Relay connection object from a list of resolved edge nodes.

    Constructs cursor strings for each edge using the node's position offset,
    then assembles the connection with pageInfo populated.

    Args:
        edges (Iterable): The resolved document instances to wrap as edges.
        start_offset (int | None): The 0-based index of the first item in *edges*
            within the full result set (used to compute cursors).
        has_previous_page (bool): Whether there are items before this page.
        has_next_page (bool): Whether there are items after this page.
        connection_type (type): The graphene connection class to instantiate.
        edge_type (type): The graphene edge class to instantiate for each node.
        pageinfo_type (type): The graphene PageInfo class.

    Returns:
        connection_type: A fully populated graphene Relay connection instance.
    """
    edges_items = [
        edge_type(
            node=node,
            cursor=offset_to_cursor((0 if start_offset is None else start_offset) + i),
        )
        for i, node in enumerate(edges)
    ]

    first_edge_cursor = edges_items[0].cursor if edges_items else None
    last_edge_cursor = edges_items[-1].cursor if edges_items else None

    return connection_type(
        edges=edges_items,
        page_info=pageinfo_type(
            start_cursor=first_edge_cursor,
            end_cursor=last_edge_cursor,
            has_previous_page=has_previous_page,
            has_next_page=has_next_page,
        ),
    )


def get_related_field_filter_args(info, model) -> dict:
    """
    Walk the GraphQL AST to find reference/list-of-reference sub-fields that carry
    filter arguments (e.g. articles(headline: "Hello")).

    Returns a dict suitable for passing into the parent queryset with __ syntax:
        {"articles": {"headline": "Hello"}}
    → caller does: qs.filter(articles__headline="Hello").select_related("articles")

    Traverses the relay wrapper fields (edges, node) transparently.
    Handles both literal argument values and GraphQL variable references.
    """
    _relay_skip = {"edges", "node", "pageInfo"}
    _arg_skip = {"first", "last", "before", "after", "id"}
    result: dict = {}

    def _traverse(selection_set):
        if not selection_set:
            return
        for sel in getattr(selection_set, "selections", []):
            if not isinstance(sel, FieldNode):
                continue
            gql_name = sel.name.value
            snake_name = to_snake_case(gql_name)
            if gql_name in _relay_skip:
                _traverse(sel.selection_set)
                continue
            if snake_name not in model._fields:
                continue
            mongo_field = model._fields[snake_name]
            inner = (
                mongo_field.field if isinstance(mongo_field, mongoengine.ListField) else mongo_field
            )
            if not isinstance(
                inner, (mongoengine.ReferenceField, mongoengine.GenericReferenceField)
            ):
                continue
            if not getattr(sel, "arguments", None):
                continue
            field_args: dict = {}
            for arg in sel.arguments:
                arg_name = to_snake_case(arg.name.value)
                if arg_name in _arg_skip:
                    continue
                if isinstance(arg.value, VariableNode):
                    val = (getattr(info, "variable_values", None) or {}).get(arg.value.name.value)
                elif hasattr(arg.value, "value"):
                    val = arg.value.value
                else:
                    continue
                if val is not None:
                    field_args[arg_name] = val
            if field_args:
                result[snake_name] = field_args

    if info and getattr(info, "field_nodes", None):
        _traverse(info.field_nodes[0].selection_set)
    return result


def get_field_resolver(
    default_async_resolver: Callable,
    default_sync_resolver: Callable,
    executor: ExecutorEnum,
    field_resolver: Optional[Callable] = None,
) -> Callable:
    """
    Helper function to get the resolver for a field

    Args:
        field_resolver: user defined resolver (optional)
        default_async_resolver: default library async resolver
        default_sync_resolver: default library sync resolver
        executor: ExecutorEnum

    Returns:
        resolver: Callable
    """
    if field_resolver is not None:
        return field_resolver

    if executor == ExecutorEnum.ASYNC:
        return default_async_resolver

    return default_sync_resolver
