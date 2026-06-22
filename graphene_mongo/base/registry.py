from graphene import Enum
from mongoengine import Document

from graphene_mongo.base.utils import ExecutorEnum


class Registry:
    """Central type registry mapping MongoEngine models to their GraphQL counterparts.

    Maintains four internal mappings:

    - model class → graphene ObjectType
    - graphene type name (str) → MongoEngine model name (str)
    - MongoEngine model name (str) → graphene ObjectType  (Documents only)
    - Python EnumMeta → graphene.Enum wrapper

    One Registry instance is shared across all types registered together,
    which allows forward references to be resolved after all types are defined.

    Args:
        executor (ExecutorEnum): Whether this registry serves SYNC or ASYNC fields.
    """

    def __init__(self, executor: ExecutorEnum):
        self.executor = executor
        self._registry = {}
        self._registry_string_map: dict[str, str] = {}
        self._registry_document_string_map = {}
        self._registry_enum = {}

    def register(self, cls):
        """Register a MongoengineObjectType (or async variant) with this registry.

        After registration every previously registered type is rescanned so that
        self-referential and forward-declared fields can be resolved now that
        the new type is available.

        Args:
            cls: A subclass of MongoengineObjectType or AsyncMongoengineObjectType.

        Raises:
            AssertionError: If *cls* is not a recognised Mongoengine object type,
                or if cls._meta.registry does not point to this Registry instance.
        """
        from ..synchronous.types import GrapheneMongoengineObjectTypes
        from ..asynchronous.types import AsyncGrapheneMongoengineObjectTypes

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
            self._registry_document_string_map[cls._meta.model.__name__] = cls
        self._registry_string_map[cls.__name__] = cls._meta.model.__name__

        # Rescan all fields
        for model, cls in self._registry.items():
            cls.rescan_fields()

    def register_enum(self, cls):
        """Register a Python Enum class and wrap it as a graphene Enum.

        Automatically appends "Enum" to the class name when not already
        suffixed, keeping the GraphQL schema name unambiguous.

        Args:
            cls (EnumMeta): The Python enum class to register.

        Raises:
            AssertionError: If *cls* is not an EnumMeta instance.
        """
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
        """Return the graphene ObjectType registered for a MongoEngine model.

        Args:
            model: A MongoEngine Document or EmbeddedDocument class.

        Returns:
            The registered graphene type class, or None if not registered.
        """
        return self._registry.get(model)

    def get_type_for_model_string(self, model_string: str) -> str | None:
        """Return the MongoEngine model name registered under a graphene type name.

        Args:
            model_string (str): The graphene type name (e.g. "ArticleType").

        Returns:
            str | None: The MongoEngine model class name, or None if not found.
        """
        return self._registry_string_map.get(model_string)

    def get_type_for_document_model(self, model):
        """Return the graphene type class for a top-level MongoEngine Document.

        Unlike get_type_for_model, this method looks up by class name
        string and only works for Document subclasses (not EmbeddedDocument).

        Args:
            model: A MongoEngine Document subclass.

        Returns:
            The registered graphene type class, or None if not registered.

        Raises:
            TypeError: If *model* is not a Document subclass.
        """
        if not issubclass(model, Document):
            raise TypeError(f"{model} is not a Document")
        return self._registry_document_string_map.get(model.__name__)

    def check_enum_already_exist(self, cls):
        """Return whether an enum class has already been registered.

        Args:
            cls (EnumMeta): The Python enum class to check.

        Returns:
            bool: True if already registered, False otherwise.
        """
        return cls in self._registry_enum

    def get_type_for_enum(self, cls):
        """Return the graphene Enum wrapper for a registered Python enum class.

        Args:
            cls (EnumMeta): The Python enum class.

        Returns:
            graphene.Enum | None: The wrapped graphene Enum, or None if
            not yet registered.
        """
        return self._registry_enum.get(cls)


registry = None
async_registry = None
inputs_registry = None
async_inputs_registry = None


def get_inputs_registry():
    """Return (creating if necessary) the singleton sync Registry for InputObjectTypes.

    Returns:
        Registry: Shared SYNC registry used for all InputObjectType registrations.
    """
    global inputs_registry
    if not inputs_registry:
        inputs_registry = Registry(executor=ExecutorEnum.SYNC)
    return inputs_registry


def get_inputs_async_registry():
    """Return (creating if necessary) the singleton async Registry for InputObjectTypes.

    Returns:
        Registry: Shared ASYNC registry used for all async InputObjectType registrations.
    """
    global async_inputs_registry
    if not async_inputs_registry:
        async_inputs_registry = Registry(executor=ExecutorEnum.ASYNC)
    return async_inputs_registry


def get_global_registry():
    """Return (creating if necessary) the singleton sync Registry.

    Returns:
        Registry: Shared SYNC registry used for all MongoengineObjectType registrations.
    """
    global registry
    if not registry:
        registry = Registry(executor=ExecutorEnum.SYNC)
    return registry


def get_global_async_registry():
    """Return (creating if necessary) the singleton async Registry.

    Returns:
        Registry: Shared ASYNC registry used for all AsyncMongoengineObjectType registrations.
    """
    global async_registry
    if not async_registry:
        async_registry = Registry(executor=ExecutorEnum.ASYNC)
    return async_registry


def reset_global_registry():
    """Reset the sync global registry and inputs registry to None.

    Called between tests to ensure a clean state.
    """
    global registry
    global inputs_registry
    registry = None
    inputs_registry = None


def reset_global_async_registry():
    """Reset the async global registry and inputs registry to None.

    Called between tests to ensure a clean state.
    """
    global async_registry
    global async_inputs_registry
    async_registry = None
    async_inputs_registry = None
