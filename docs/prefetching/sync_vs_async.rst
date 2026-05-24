Sync vs Async
=============

Both execution modes share the same pre-fetching logic. The difference is the
QuerySet manager:

Sync (``MongoengineObjectType``)
    Uses ``model.objects``.

Async (``AsyncMongoengineObjectType``)
    Uses ``model.aobjects``. The pipeline builder compiles everything into a
    single ``aggregate()`` call.
