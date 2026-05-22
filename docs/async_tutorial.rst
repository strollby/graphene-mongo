Async Tutorial — FastAPI
========================

graphene-mongo ships a first-class async API built on Motor (asyncio MongoDB driver).
This tutorial shows how to wire it up with FastAPI.

The full source is in
`examples/fastapi_mongoengine <https://github.com/graphql-python/graphene-mongo/tree/master/examples/fastapi_mongoengine>`__.

For the synchronous Flask tutorial see :doc:`tutorial`.

How the Async API Works
-----------------------

The async API mirrors the sync API but uses:

- ``AsyncMongoengineObjectType`` instead of ``MongoengineObjectType``
- ``AsyncMongoengineConnectionField`` instead of ``MongoengineConnectionField``
- ``schema.execute_async()`` instead of ``schema.execute()``
- ``mongoengine.async_connect()`` in addition to ``mongoengine.connect()``

Internally, ``AsyncMongoengineConnectionField`` calls ``select_related()`` on
the queryset, resolving all referenced documents in a **single** MongoDB
``$aggregate`` pipeline — no N+1 queries.

Setup
-----

.. code:: bash

    mkdir fastapi_graphene_mongo && cd fastapi_graphene_mongo
    uv init
    uv add fastapi "uvicorn[standard]" graphene-mongo mongoengine mongomock

Models
------

.. code:: python

    # models.py
    import mongoengine

    class Author(mongoengine.Document):
        meta = {"collection": "authors"}
        name = mongoengine.StringField(required=True)
        birth_year = mongoengine.IntField()
        nationality = mongoengine.StringField()

    class Book(mongoengine.Document):
        meta = {"collection": "books"}
        title = mongoengine.StringField(required=True)
        published_year = mongoengine.IntField()
        genre = mongoengine.StringField()
        author = mongoengine.ReferenceField(Author)
        tags = mongoengine.ListField(mongoengine.StringField())

Schema
------

Use ``AsyncMongoengineObjectType`` and ``AsyncMongoengineConnectionField``:

.. code:: python

    # schema.py
    import graphene
    from graphene.relay import Node
    from graphene_mongo import AsyncMongoengineConnectionField, AsyncMongoengineObjectType
    from models import Author as AuthorModel, Book as BookModel

    class AuthorType(AsyncMongoengineObjectType):
        class Meta:
            model = AuthorModel
            interfaces = (Node,)
            filter_fields = {
                "name": ["exact", "icontains", "istartswith"],
                "nationality": ["exact"],
            }

    class BookType(AsyncMongoengineObjectType):
        class Meta:
            model = BookModel
            interfaces = (Node,)
            filter_fields = {
                "title": ["exact", "icontains"],
                "genre": ["exact"],
                "published_year": ["exact", "gte", "lte"],
            }

    class Query(graphene.ObjectType):
        node = Node.Field()
        books = AsyncMongoengineConnectionField(BookType)
        authors = AsyncMongoengineConnectionField(AuthorType)

    schema = graphene.Schema(query=Query, types=[AuthorType, BookType])

Async Mutations
---------------

Mutation ``mutate`` methods can be ``async def`` — use ``await`` to call
``aobjects`` (Motor-backed queryset) and ``asave()`` / ``adelete()``:

.. code:: python

    class CreateBook(graphene.Mutation):
        class Arguments:
            title = graphene.String(required=True)
            genre = graphene.String()
            author_id = graphene.ID()

        book = graphene.Field(BookType)

        async def mutate(self, info, title, genre=None, author_id=None):
            from graphql_relay import from_global_id
            author = None
            if author_id:
                author = await AuthorModel.aobjects.get(pk=from_global_id(author_id)[1])
            book = BookModel(title=title, genre=genre, author=author)
            await book.asave()
            return CreateBook(book=book)

    class DeleteBook(graphene.Mutation):
        class Arguments:
            id = graphene.ID(required=True)

        success = graphene.Boolean()

        async def mutate(self, info, id):
            from graphql_relay import from_global_id
            try:
                book = await BookModel.aobjects.get(pk=from_global_id(id)[1])
                await book.adelete()
                return DeleteBook(success=True)
            except BookModel.DoesNotExist:
                return DeleteBook(success=False)

    class Mutation(graphene.ObjectType):
        create_book = CreateBook.Field()
        delete_book = DeleteBook.Field()

FastAPI Integration
-------------------

FastAPI uses a lifespan context manager for startup/shutdown. Both
``mongoengine.connect()`` (for sync operations) and
``mongoengine.async_connect()`` (for Motor) are needed:

.. code:: python

    # app.py
    from contextlib import asynccontextmanager
    import mongoengine
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse
    from schema import schema

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        mongoengine.connect("library_db")
        await mongoengine.async_connect("library_db")
        yield
        mongoengine.disconnect()

    app = FastAPI(title="Library API", lifespan=lifespan)

    @app.post("/graphql")
    async def graphql(request: Request):
        body = await request.json()
        result = await schema.execute_async(
            body["query"],
            variable_values=body.get("variables"),
            operation_name=body.get("operationName"),
        )
        errors = [{"message": str(e)} for e in result.errors] if result.errors else None
        return JSONResponse({"data": result.data, "errors": errors})

Running
-------

.. code:: bash

    uv run uvicorn app:app --reload

Example Queries
---------------

Fetch all books with their author (resolved in **one** aggregation query):

.. code:: graphql

    {
      books {
        edges {
          node {
            title
            genre
            author { name nationality }
          }
        }
      }
    }

Filter and paginate:

.. code:: graphql

    {
      books(genre: "Dystopian", first: 5) {
        edges { node { title publishedYear } }
        pageInfo { hasNextPage endCursor }
      }
    }

Create a book:

.. code:: graphql

    mutation {
      createBook(title: "Brave New World", genre: "Dystopian") {
        book { id title }
      }
    }

N+1 Elimination
---------------

``AsyncMongoengineConnectionField`` automatically calls ``select_related()``
based on which fields are present in the query. For the query above,
``author`` is pre-fetched in the same aggregation as the books — no separate
per-book query. This applies to deeply nested references too:

.. code:: graphql

    # one aggregate query regardless of depth
    {
      books {
        edges {
          node {
            title
            author { name }     # pre-fetched via $lookup
          }
        }
      }
    }

Without pagination args (``first`` / ``last`` / ``before`` / ``after``), the
``count()`` call is also skipped, reducing the total to **one** DB query.