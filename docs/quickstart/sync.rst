Synchronous
===========

1. Connect to MongoDB
---------------------

.. code:: python

    import mongoengine
    mongoengine.connect("mydb")

2. Define a document
---------------------

.. code:: python

    import mongoengine

    class Article(mongoengine.Document):
        meta = {"collection": "articles"}
        title = mongoengine.StringField(required=True)
        published = mongoengine.BooleanField(default=False)

3. Create a GraphQL type
-------------------------

.. code:: python

    from graphene.relay import Node
    from graphene_mongo import MongoengineObjectType

    class ArticleType(MongoengineObjectType):
        class Meta:
            model = Article
            interfaces = (Node,)

``MongoengineObjectType`` inspects the MongoEngine model and converts each field
to the appropriate GraphQL scalar type automatically. Adding ``Node`` to
``interfaces`` enables Relay cursor pagination and global node lookups.

4. Build the schema
--------------------

.. code:: python

    import graphene
    from graphene_mongo import MongoengineConnectionField

    class Query(graphene.ObjectType):
        node = Node.Field()
        articles = MongoengineConnectionField(ArticleType)

    schema = graphene.Schema(query=Query)

``MongoengineConnectionField`` handles pagination arguments (``first``, ``after``,
``last``, ``before``), ordering, and pre-fetching of referenced documents.

5. Query the schema
--------------------

.. code:: python

    result = schema.execute("""
        {
            articles {
                edges {
                    node { id title published }
                }
            }
        }
    """)
    print(result.data)

Full example
------------

.. code:: python

    import graphene
    import mongoengine
    from graphene.relay import Node
    from graphene_mongo import MongoengineObjectType, MongoengineConnectionField

    mongoengine.connect("mydb")

    class Article(mongoengine.Document):
        meta = {"collection": "articles"}
        title = mongoengine.StringField(required=True)
        published = mongoengine.BooleanField(default=False)

    class ArticleType(MongoengineObjectType):
        class Meta:
            model = Article
            interfaces = (Node,)

    class Query(graphene.ObjectType):
        node = Node.Field()
        articles = MongoengineConnectionField(ArticleType)

    schema = graphene.Schema(query=Query)
    result = schema.execute("{ articles { edges { node { title } } } }")
    print(result.data)