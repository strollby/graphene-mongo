Graphene-Mongo
==============

A `Mongoengine <http://mongoengine.org/>`__ integration for
`Graphene <http://graphene-python.org/>`__. Supports both synchronous and
async (Motor/asyncio) execution.

Features
--------

- Automatic GraphQL type generation from Mongoengine models
- Relay-compatible connection fields with pagination and filtering
- **Sync** (``MongoengineObjectType``, ``MongoengineConnectionField``) and
  **Async** (``AsyncMongoengineObjectType``, ``AsyncMongoengineConnectionField``) APIs
- ``select_related`` — eliminates N+1 queries by pre-fetching referenced documents
  in a single MongoDB ``$aggregate`` pipeline
- Works with Flask, Falcon, FastAPI, Django, or any Python web framework
- Full support for mutations, embedded documents, reference fields, and inheritance

Installation
------------

.. code:: bash

    # with uv (recommended)
    uv add graphene-mongo

    # with pip
    pip install graphene-mongo

Quick Start
-----------

**Synchronous (Flask / Django / Falcon)**

.. code:: python

    import graphene
    from graphene.relay import Node
    from graphene_mongo import MongoengineObjectType, MongoengineConnectionField
    from mongoengine import Document, StringField, connect

    connect("mydb")

    class Article(Document):
        title = StringField()

    class ArticleType(MongoengineObjectType):
        class Meta:
            model = Article
            interfaces = (Node,)

    class Query(graphene.ObjectType):
        node = Node.Field()
        articles = MongoengineConnectionField(ArticleType)

    schema = graphene.Schema(query=Query)

**Asynchronous (FastAPI / async frameworks)**

.. code:: python

    import graphene
    import mongoengine
    from graphene.relay import Node
    from graphene_mongo import AsyncMongoengineObjectType, AsyncMongoengineConnectionField

    class ArticleType(AsyncMongoengineObjectType):
        class Meta:
            model = Article
            interfaces = (Node,)

    class Query(graphene.ObjectType):
        node = Node.Field()
        articles = AsyncMongoengineConnectionField(ArticleType)

    schema = graphene.Schema(query=Query)

    # execute
    result = await schema.execute_async("{ articles { edges { node { title } } } }")

Contents
--------

.. toctree::
    :maxdepth: 2

    tutorial
    async_tutorial
    fields