Sync vs Async: Key Differences
================================

Both modes expose the same GraphQL schema and support Relay pagination,
filtering, pre-fetching, and mutations. The only differences are the
classes and managers you use.

Type class
    Sync: ``MongoengineObjectType`` — Async: ``AsyncMongoengineObjectType``

Connection field
    Sync: ``MongoengineConnectionField`` — Async: ``AsyncMongoengineConnectionField``

QuerySet manager
    Sync: ``model.objects`` — Async: ``model.aobjects``

Schema execution
    Sync: ``schema.execute()`` — Async: ``await schema.execute_async()``

Resolvers
    Sync: plain ``def`` — Async: ``async def``

Both modes apply ``select_related`` automatically — referenced documents are
pre-fetched in a single MongoDB aggregation, not lazy-loaded per document.
See :doc:`/prefetching/index` for details.