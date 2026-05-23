from graphene.types.interface import Interface, InterfaceOptions
from graphene.types.objecttype import ObjectType, ObjectTypeOptions
from graphene.utils.str_converters import to_snake_case

from .fields import AsyncMongoengineConnectionField
from ..base.registry import get_global_async_registry, get_inputs_async_registry
from ..base.types import create_graphene_generic_class as _create
from ..base.utils import ExecutorEnum, get_query_fields, get_select_related_paths


def create_graphene_generic_class_async(object_type, option_type):
    """Create an async MongoengineObjectType base class and its options class.

    Thin wrapper around :func:`~graphene_mongo.base.types.create_graphene_generic_class`
    that injects async-specific dependencies (async registry factories, async connection
    field class, and an ``async def get_node`` classmethod).

    ``get_node`` is injected via attribute assignment rather than subclassing to avoid
    triggering ``__init_subclass_with_meta__`` on the intermediate class.

    Args:
        object_type: graphene base class to inherit from
            (e.g. ``ObjectType``, ``Interface``).
        option_type: Matching options class
            (e.g. ``ObjectTypeOptions``, ``InterfaceOptions``).

    Returns:
        tuple[type, type]:
            ``(GenericType, Options)`` — the generated base class and its options class.
            ``GenericType.get_node`` is an async classmethod that uses
            ``await model.aobjects.only(*fields).get(pk=id)``.
    """
    GenericType, Options = _create(
        object_type,
        option_type,
        executor=ExecutorEnum.ASYNC,
        global_registry_factory=get_global_async_registry,
        inputs_registry_factory=get_inputs_async_registry,
        default_connection_field_class=AsyncMongoengineConnectionField,
    )

    @classmethod
    async def get_node(cls, info, id):
        required_fields = list()
        for field in cls._meta.required_fields:
            if field in cls._meta.model._fields_ordered:
                required_fields.append(field)
        queried_fields = get_query_fields(info)
        if cls._meta.name in queried_fields:
            queried_fields = queried_fields[cls._meta.name]
        for field in queried_fields:
            if to_snake_case(field) in cls._meta.model._fields_ordered:
                required_fields.append(to_snake_case(field))
        required_fields = list(set(required_fields))
        related = get_select_related_paths(cls._meta.model, queried_fields)
        qs = cls._meta.model.aobjects.only(*required_fields)
        if related:
            qs = qs.select_related(*related)
        return await qs.get(pk=id)

    GenericType.get_node = get_node
    return GenericType, Options


(
    AsyncMongoengineObjectType,
    AsyncMongoengineObjectTypeOptions,
) = create_graphene_generic_class_async(ObjectType, ObjectTypeOptions)

(
    AsyncMongoengineInterfaceType,
    MongoengineInterfaceTypeOptions,
) = create_graphene_generic_class_async(Interface, InterfaceOptions)

AsyncGrapheneMongoengineObjectTypes = (
    AsyncMongoengineObjectType,
    AsyncMongoengineInterfaceType,
)
