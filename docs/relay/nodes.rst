Nodes
=====

Enabling Relay
--------------

Add ``Node`` to ``interfaces`` in the ``Meta`` class:

.. code:: python

    from graphene.relay import Node
    from graphene_mongo import MongoengineObjectType, MongoengineConnectionField

    class ArticleType(MongoengineObjectType):
        class Meta:
            model = Article
            interfaces = (Node,)

    class Query(graphene.ObjectType):
        node = Node.Field()                    # global node lookup
        articles = MongoengineConnectionField(ArticleType)

Node.Field() — single-document lookup
--------------------------------------

``Node.Field()`` on the query enables fetching any registered type by its global
Relay ID:

.. code:: graphql

    query {
        node(id: "QXJ0aWNsZVR5cGU6NjY...") {
            ... on ArticleType {
                title
                editor { firstName }
            }
        }
    }

The default ``get_node`` implementation already applies ``select_related``
automatically — it inspects the selection set and pre-fetches only what the
client requested.

Overriding get_node
-------------------

If you override ``get_node`` for custom filtering or access control, replicate
the pre-fetching yourself to avoid unhydrated references:

.. code:: python

    from graphene_mongo import get_query_fields, get_select_related_paths

    class ReporterNode(AsyncMongoengineObjectType):
        class Meta:
            model = Reporter
            interfaces = (Node,)

        @classmethod
        async def get_node(cls, info, id):
            queried = get_query_fields(info)
            paths = get_select_related_paths(cls._meta.model, queried)
            qs = cls._meta.model.aobjects.filter(pk=id)
            if paths:
                qs = qs.select_related(*paths)
            return await qs.first()

Omitting ``select_related`` here will cause referenced fields to resolve to
``None`` or raise an error.

Async Relay
-----------

Replace ``MongoengineObjectType`` and ``MongoengineConnectionField`` with their
async counterparts:

.. code:: python

    from graphene_mongo import AsyncMongoengineObjectType, AsyncMongoengineConnectionField

    class ArticleType(AsyncMongoengineObjectType):
        class Meta:
            model = Article
            interfaces = (Node,)

    class Query(graphene.ObjectType):
        node = Node.Field()
        articles = AsyncMongoengineConnectionField(ArticleType)

    schema = graphene.Schema(query=Query)
    result = await schema.execute_async("{ articles { edges { node { title } } } }")
