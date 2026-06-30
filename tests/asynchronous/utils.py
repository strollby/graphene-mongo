from mongoengine.context_managers import async_query_counter

from graphene_mongo import registry


def with_local_async_registry(func):
    def inner(*args, **kwargs):
        old = registry.async_registry
        registry.reset_global_async_registry()
        try:
            retval = func(*args, **kwargs)
        except Exception as e:
            registry.async_registry = old
            raise e
        else:
            registry.async_registry = old
            return retval

    return inner


async def execute_count(schema, query, **kwargs):
    """Execute a GraphQL query and return (result, query_count)."""
    async with async_query_counter() as q:
        result = await schema.execute_async(query, **kwargs)
        count = await q.int()
    return result, count
