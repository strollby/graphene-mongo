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