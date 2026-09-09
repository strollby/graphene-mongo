from mongoengine.context_managers import async_query_counter

from . import nodes
from graphene_mongo import AsyncMongoengineConnectionField


async def test_default_resolver_with_colliding_objects_field():
    field = AsyncMongoengineConnectionField(nodes.ErroneousModelAsyncNode)

    async with async_query_counter() as q:
        connection = await field.default_resolver(None, {})
        count = await q.int()
    assert 0 == len(connection.iterable)
    assert count == 0


async def test_default_resolver_connection_list_length(fixtures):
    field = AsyncMongoengineConnectionField(nodes.ArticleAsyncNode)

    async with async_query_counter() as q:
        connection = await field.default_resolver(None, {}, **{"first": 1})
        count = await q.int()
    assert hasattr(connection, "list_length")
    assert connection.list_length == 1
    assert count == 2
