Asynchronous
============

Async mode requires both a standard MongoEngine connection (for schema
introspection) and an async Motor connection (for queries):

1. Connect to MongoDB
---------------------

.. code:: python

    import mongoengine
    mongoengine.connect("mydb")
    mongoengine.async_connect("mydb")

2. Define a document
---------------------

.. code:: python

    import mongoengine

    class Article(mongoengine.Document):
        meta = {"collection": "articles"}
        title = mongoengine.StringField(required=True)
        published = mongoengine.BooleanField(default=False)

3. Create an async GraphQL type
---------------------------------

.. code:: python

    from graphene.relay import Node
    from graphene_mongo import AsyncMongoengineObjectType

    class ArticleType(AsyncMongoengineObjectType):
        class Meta:
            model = Article
            interfaces = (Node,)

``AsyncMongoengineObjectType`` uses ``model.aobjects`` (Motor) for all database
access. Field mapping, Relay pagination, and pre-fetching work identically to
the sync version.

4. Build the schema
--------------------

.. code:: python

    import graphene
    from graphene_mongo import AsyncMongoengineConnectionField

    class Query(graphene.ObjectType):
        node = Node.Field()
        articles = AsyncMongoengineConnectionField(ArticleType)

    schema = graphene.Schema(query=Query)

5. Execute async queries
-------------------------

.. code:: python

    import asyncio

    result = asyncio.run(
        schema.execute_async("{ articles { edges { node { title } } } }")
    )
    print(result.data)

Full example
------------

.. code:: python

    import asyncio
    import graphene
    import mongoengine
    from graphene.relay import Node
    from graphene_mongo import AsyncMongoengineObjectType, AsyncMongoengineConnectionField

    mongoengine.connect("mydb")
    mongoengine.async_connect("mydb")

    class Article(mongoengine.Document):
        meta = {"collection": "articles"}
        title = mongoengine.StringField(required=True)
        published = mongoengine.BooleanField(default=False)

    class ArticleType(AsyncMongoengineObjectType):
        class Meta:
            model = Article
            interfaces = (Node,)

    class Query(graphene.ObjectType):
        node = Node.Field()
        articles = AsyncMongoengineConnectionField(ArticleType)

    schema = graphene.Schema(query=Query)
    result = asyncio.run(
        schema.execute_async("{ articles { edges { node { title } } } }")
    )
    print(result.data)