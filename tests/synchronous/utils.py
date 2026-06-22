from mongoengine.context_managers import query_counter

from graphene_mongo import registry


def with_local_registry(func):
    def inner(*args, **kwargs):
        old = registry.get_global_registry()
        registry.reset_global_registry()
        try:
            retval = func(*args, **kwargs)
        except Exception as e:
            registry.registry = old
            raise e
        else:
            registry.registry = old
            return retval

    return inner


def execute_count(schema, query, **kwargs):
    """Execute a GraphQL query and return (result, query_count)."""
    with query_counter() as q:
        result = schema.execute(query, **kwargs)
        count = int(q)
    return result, count
