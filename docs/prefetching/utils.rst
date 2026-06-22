Utility Functions
=================

Connection fields call these utilities internally. You can use them in custom
resolvers too:

.. code:: python

    from graphene_mongo import get_query_fields, get_select_related_paths

    # Derive the paths the client actually queried
    queried = get_query_fields(info)        # {"editor": {"firstName": {}}, ...}
    paths = get_select_related_paths(Reporter, queried)  # ["editor", "editor__company"]

    # Apply only what the client asked for
    qs = Reporter.aobjects.filter(active=True).select_related(*paths)

``get_query_fields`` returns the nested selection-set dict from the GraphQL AST.
``get_select_related_paths`` walks that dict against the MongoEngine model and
returns ``__``-separated paths suitable for ``QuerySet.select_related``.

Custom List resolvers
---------------------

Connection fields apply ``select_related`` automatically. When you write a
``graphene.List`` resolver or a single-document resolver outside the connection
pipeline, you are responsible for calling ``select_related`` yourself:

.. code:: python

    from graphene_mongo import get_query_fields, get_select_related_paths

    # Hard-coded — over-fetches and breaks silently when model changes
    async def resolve_reporter(self, info):
        return await Reporter.aobjects.select_related("articles", "company").first()

    # Query-driven — fetches only what the client asked for
    async def resolve_reporter(self, info):
        queried = get_query_fields(info)
        paths = get_select_related_paths(Reporter, queried)
        return await Reporter.aobjects.select_related(*paths).first()
