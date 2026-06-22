Connections
===========

graphene-mongo ships full support for the
`Relay cursor pagination spec <https://relay.dev/graphql/connections.htm>`__.

Pagination arguments
---------------------

All connection fields support the standard Relay pagination arguments:

``first``
    Return the first N edges.

``after``
    Return edges after this cursor.

``last``
    Return the last N edges.

``before``
    Return edges before this cursor.

Example query:

.. code:: graphql

    query {
        articles(first: 10, after: "YXJyYXljb25uZWN0aW9u...") {
            pageInfo {
                hasNextPage
                hasPreviousPage
                startCursor
                endCursor
            }
            edges {
                cursor
                node {
                    id
                    title
                }
            }
        }
    }
