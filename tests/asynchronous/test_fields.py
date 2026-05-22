import pytest

from . import nodes
from graphene_mongo import AsyncMongoengineConnectionField


@pytest.mark.asyncio
async def test_default_resolver_with_colliding_objects_field_async():
    field = AsyncMongoengineConnectionField(nodes.ErroneousModelAsyncNode)

    connection = await field.default_resolver(None, {})
    assert 0 == len(connection.iterable)


@pytest.mark.asyncio
async def test_default_resolver_connection_list_length_async(fixtures):
    field = AsyncMongoengineConnectionField(nodes.ArticleAsyncNode)

    connection = await field.default_resolver(None, {}, **{"first": 1})
    assert hasattr(connection, "list_length")
    assert connection.list_length == 1