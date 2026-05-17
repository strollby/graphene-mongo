from graphene import Enum
from mongoengine import Document

from graphene_mongo.utils import ExecutorEnum


class Registry(object):
    def __init__(self, executor: ExecutorEnum):
        self.executor = executor
        self._registry = {}
        self._registry_document_map = {}
        self._registry_string_map = {}
        self._registry_enum = {}

    def register(self, cls):
        from .types import GrapheneMongoengineObjectTypes
        from .types_async import AsyncGrapheneMongoengineObjectTypes

        assert issubclass(cls, GrapheneMongoengineObjectTypes) or issubclass(
            cls, AsyncGrapheneMongoengineObjectTypes
        ), (
            'Only Mongoengine/Async Mongoengine object types can be registered, received "{}"'.format(
                cls.__name__
            )
        )
        assert cls._meta.registry == self, "Registry for a Model have to match."
        self._registry[cls._meta.model] = cls
        if issubclass(cls._meta.model, Document):
            self._registry_document_map[cls._meta.model.__name__] = cls
        self._registry_string_map[cls.__name__] = cls._meta.model.__name__

        # Rescan all fields
        for model, cls in self._registry.items():
            cls.rescan_fields()

    def register_enum(self, cls):
        from enum import EnumMeta

        assert isinstance(cls, EnumMeta), (
            f'Only EnumMeta can be registered, received "{cls.__name__}"'
        )
        if not cls.__name__.endswith("Enum"):
            name = cls.__name__ + "Enum"
        else:
            name = cls.__name__
        cls.__name__ = name
        self._registry_enum[cls] = Enum.from_enum(cls)

    def get_type_for_model(self, model):
        return self._registry.get(model)

    def get_type_for_document_model(self, model):
        if not issubclass(model, Document):
            raise TypeError(f"{model} is not a Document")
        return self._registry_document_map.get(model.__name__)

    def check_enum_already_exist(self, cls):
        return cls in self._registry_enum

    def get_type_for_enum(self, cls):
        return self._registry_enum.get(cls)


registry = None
async_registry = None
inputs_registry = None
async_inputs_registry = None


def get_inputs_registry():
    global inputs_registry
    if not inputs_registry:
        inputs_registry = Registry(executor=ExecutorEnum.SYNC)
    return inputs_registry


def get_inputs_async_registry():
    global async_inputs_registry
    if not async_inputs_registry:
        async_inputs_registry = Registry(executor=ExecutorEnum.ASYNC)
    return async_inputs_registry


def get_global_registry():
    global registry
    if not registry:
        registry = Registry(executor=ExecutorEnum.SYNC)
    return registry


def get_global_async_registry():
    global async_registry
    if not async_registry:
        async_registry = Registry(executor=ExecutorEnum.ASYNC)
    return async_registry


def reset_global_registry():
    global registry
    global inputs_registry
    registry = None
    inputs_registry = None


def reset_global_async_registry():
    global async_registry
    global async_inputs_registry
    async_registry = None
    async_inputs_registry = None
