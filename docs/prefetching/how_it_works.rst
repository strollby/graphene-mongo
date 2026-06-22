How It Works
============

When a connection field resolves, graphene-mongo inspects the incoming GraphQL
selection set *before* the query runs. It walks every field the client requested
and collects the MongoEngine reference paths that need to be resolved — including
nested references (e.g. ``article → editor → company``). These paths are passed
to MongoEngine's ``select_related``, which compiles them into a single MongoDB
aggregation pipeline using ``$lookup`` stages.

.. code:: graphql

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

The library detects that ``editor`` and ``editor.company`` are referenced fields,
then issues:

.. code:: python

    Article.aobjects.select_related("editor", "editor__company")

This becomes **one** aggregation with two ``$lookup`` stages — no N+1, no lazy
deref, no hidden thread pools.
