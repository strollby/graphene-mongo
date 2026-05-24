Graphene-Mongo
==============

graphene-mongo is a `MongoEngine <https://mongoengine-odm.readthedocs.io/>`__ integration for
`Graphene <http://graphene-python.org/>`__ that lets you expose MongoDB documents as a
fully-featured GraphQL API with minimal boilerplate.

It uses a *code-first* approach — you write Python, not GraphQL SDL. MongoEngine document
fields are mapped to GraphQL scalar types automatically. You get Relay cursor pagination,
filtering, and N+1-free pre-fetching out of the box.

Contents:

.. toctree::
   :maxdepth: 2

   installation
   quickstart/index
   types/index
   prefetching/index
   relay/index
   telemetry/index
   examples/index