from graphql import GraphQLResolveInfo

from .dataloader import MongoDataLoader

DATALOADER_CONTEXT_ATTRIBUTE = "_mongo_dataloader"


def get_dataloader(info: GraphQLResolveInfo) -> MongoDataLoader:
    """
    Get the MongoDataLoader() from info context or operation
    """
    data_point = info.context or info.operation

    if not hasattr(data_point, DATALOADER_CONTEXT_ATTRIBUTE):
        setattr(data_point, DATALOADER_CONTEXT_ATTRIBUTE, MongoDataLoader(info=info))

    return getattr(data_point, DATALOADER_CONTEXT_ATTRIBUTE)