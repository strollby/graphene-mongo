Getting Started
===============

Both sync and async APIs follow the same pattern: define a MongoEngine document,
wrap it in an ObjectType, attach it to a schema. graphene-mongo converts your
MongoEngine fields to GraphQL types automatically — no manual type declarations
needed.

Add ``interfaces = (Node,)`` to get Relay cursor pagination, filtering,
and N+1-free pre-fetching out of the box.

.. toctree::
   :maxdepth: 1

   sync
   async
   differences