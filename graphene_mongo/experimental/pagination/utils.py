from graphql_relay import offset_to_cursor

from ...utils import ast_to_dict, collect_query_fields


def find_skip_and_limit(first, last, after, before, page_offset, page_limit, count=None):
    skip = 0
    limit = None

    if last is not None and count is None:
        raise ValueError("Count Missing")

    # Pagination Logic
    if page_offset is not None and page_limit is not None:
        skip = page_offset * page_limit
        limit = page_limit
        return skip, limit
    # End of Pagination Logic

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
    page_count,
):
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
        page_count=page_count,
    )


def has_page_count(info):
    """A convenience function to call collect_query_fields with info
    for retrieving if page_count details are required

    Args:
        info (ResolveInfo)

    Returns:
        bool: True if it received pageCount
    """

    fragments = {}
    if not info:
        return True  # Returning True if invalid info is provided
    node = ast_to_dict(info.field_nodes[0])
    variables = info.variable_values

    for name, value in info.fragments.items():
        fragments[name] = ast_to_dict(value)

    query = collect_query_fields(node, fragments, variables)
    return next((True for x in query.keys() if x.lower() == "pagecount"), False)
