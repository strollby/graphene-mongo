from functools import singledispatch

import graphene
from graphene.types.json import JSONString
from graphene.utils.str_converters import to_camel_case
import mongoengine

from . import advanced_types
from .utils import (
    ExecutorEnum,
    get_field_description,
    get_field_is_required,
    get_document,
)


class MongoEngineConversionError(Exception):
    """Raised when a MongoEngine field type has no registered graphene converter."""


@singledispatch
def convert_mongoengine_field(field, registry=None, executor: ExecutorEnum = ExecutorEnum.SYNC):
    """Convert a MongoEngine field instance into the corresponding graphene field.

    Dispatches via @singledispatch to a type-specific handler registered
    below. All handlers share the same signature so callers do not need to know
    the concrete field type.

    Args:
        field: A MongoEngine field instance (e.g. StringField, ReferenceField).
        registry (Registry | None): Active type registry used to resolve
            referenced document types to their graphene equivalents.
        executor (ExecutorEnum): SYNC or ASYNC — controls which resolver
            variant is attached to relationship fields.

    Returns:
        A graphene field instance: graphene.String, graphene.Field,
        graphene.List, graphene.Dynamic, etc.

    Raises:
        MongoEngineConversionError: If no handler is registered for *field*'s type.
    """
    raise MongoEngineConversionError(
        "Don't know how to convert the MongoEngine field %s (%s)" % (field, field.__class__)
    )


@convert_mongoengine_field.register(mongoengine.EmailField)
@convert_mongoengine_field.register(mongoengine.StringField)
@convert_mongoengine_field.register(mongoengine.URLField)
def convert_field_to_string(field, registry=None, executor: ExecutorEnum = ExecutorEnum.SYNC):
    """Convert EmailField / StringField / URLField → graphene.String."""
    return graphene.String(
        description=get_field_description(field, registry),
        required=get_field_is_required(field, registry),
    )


@convert_mongoengine_field.register(mongoengine.UUIDField)
@convert_mongoengine_field.register(mongoengine.ObjectIdField)
def convert_field_to_id(field, registry=None, executor: ExecutorEnum = ExecutorEnum.SYNC):
    """Convert UUIDField / ObjectIdField → graphene.ID."""
    return graphene.ID(
        description=get_field_description(field, registry),
        required=get_field_is_required(field, registry),
    )


@convert_mongoengine_field.register(mongoengine.IntField)
@convert_mongoengine_field.register(mongoengine.SequenceField)
def convert_field_to_int(field, registry=None, executor: ExecutorEnum = ExecutorEnum.SYNC):
    """Convert IntField / SequenceField → graphene.Int."""
    return graphene.Int(
        description=get_field_description(field, registry),
        required=get_field_is_required(field, registry),
    )


@convert_mongoengine_field.register(mongoengine.BooleanField)
def convert_field_to_boolean(field, registry=None, executor: ExecutorEnum = ExecutorEnum.SYNC):
    """Convert BooleanField → graphene.Boolean."""
    return graphene.Boolean(
        description=get_field_description(field, registry),
        required=get_field_is_required(field, registry),
    )


@convert_mongoengine_field.register(mongoengine.FloatField)
def convert_field_to_float(field, registry=None, executor: ExecutorEnum = ExecutorEnum.SYNC):
    """Convert FloatField → graphene.Float."""
    return graphene.Float(
        description=get_field_description(field, registry),
        required=get_field_is_required(field, registry),
    )


@convert_mongoengine_field.register(mongoengine.Decimal128Field)
@convert_mongoengine_field.register(mongoengine.DecimalField)
def convert_field_to_decimal(field, registry=None, executor: ExecutorEnum = ExecutorEnum.SYNC):
    """Convert Decimal128Field / DecimalField → graphene.Decimal."""
    return graphene.Decimal(
        description=get_field_description(field, registry),
        required=get_field_is_required(field, registry),
    )


@convert_mongoengine_field.register(mongoengine.DateTimeField)
def convert_field_to_datetime(field, registry=None, executor: ExecutorEnum = ExecutorEnum.SYNC):
    """Convert DateTimeField → graphene.DateTime."""
    return graphene.DateTime(
        description=get_field_description(field, registry),
        required=get_field_is_required(field, registry),
    )


@convert_mongoengine_field.register(mongoengine.DateField)
def convert_field_to_date(field, registry=None, executor: ExecutorEnum = ExecutorEnum.SYNC):
    """Convert DateField → graphene.Date."""
    return graphene.Date(
        description=get_field_description(field, registry),
        required=get_field_is_required(field, registry),
    )


@convert_mongoengine_field.register(mongoengine.DictField)
@convert_mongoengine_field.register(mongoengine.MapField)
def convert_field_to_jsonstring(field, registry=None, executor: ExecutorEnum = ExecutorEnum.SYNC):
    """Convert DictField / MapField → graphene JSONString (arbitrary JSON blob)."""
    return JSONString(
        description=get_field_description(field, registry),
        required=get_field_is_required(field, registry),
    )


@convert_mongoengine_field.register(mongoengine.PointField)
def convert_point_to_field(field, registry=None, executor: ExecutorEnum = ExecutorEnum.SYNC):
    """Convert PointField → graphene.Field(PointFieldType)."""
    return graphene.Field(
        advanced_types.PointFieldType,
        description=get_field_description(field, registry),
        required=get_field_is_required(field, registry),
    )


@convert_mongoengine_field.register(mongoengine.PolygonField)
def convert_polygon_to_field(field, registry=None, executor: ExecutorEnum = ExecutorEnum.SYNC):
    """Convert PolygonField → graphene.Field(PolygonFieldType)."""
    return graphene.Field(
        advanced_types.PolygonFieldType,
        description=get_field_description(field, registry),
        required=get_field_is_required(field, registry),
    )


@convert_mongoengine_field.register(mongoengine.MultiPolygonField)
def convert_multipolygon_to_field(field, registry=None, executor: ExecutorEnum = ExecutorEnum.SYNC):
    """Convert MultiPolygonField → graphene.Field(MultiPolygonFieldType)."""
    return graphene.Field(
        advanced_types.MultiPolygonFieldType,
        description=get_field_description(field, registry),
        required=get_field_is_required(field, registry),
    )


@convert_mongoengine_field.register(mongoengine.FileField)
def convert_file_to_field(field, registry=None, executor: ExecutorEnum = ExecutorEnum.SYNC):
    """Convert FileField → graphene.Field(FileFieldType)."""
    return graphene.Field(
        advanced_types.FileFieldType,
        description=get_field_description(field, registry),
        required=get_field_is_required(field, registry),
    )


@convert_mongoengine_field.register(mongoengine.AwareDateTimeField)
def convert_aware_datetime_to_field(field, registry=None, executor: ExecutorEnum = ExecutorEnum.SYNC):
    """Convert AwareDateTimeField → AwareDateTimeScalar (RFC 9557 IXDTF).

    Serialises to "2024-05-16T12:00:00+09:00[Asia/Tokyo]" — local wall-clock
    time with the UTC offset and IANA timezone annotation per RFC 9557.
    """
    return advanced_types.AwareDateTimeScalar(
        description=get_field_description(field, registry),
        required=get_field_is_required(field, registry),
    )


@convert_mongoengine_field.register(mongoengine.ListField)
@convert_mongoengine_field.register(mongoengine.EmbeddedDocumentListField)
@convert_mongoengine_field.register(mongoengine.GeoPointField)
def convert_field_to_list(field, registry=None, executor: ExecutorEnum = ExecutorEnum.SYNC):
    """Convert ListField / EmbeddedDocumentListField / GeoPointField → graphene.List.

    For lists of references a resolver is attached that lazily fetches the
    referenced documents. For lists of embedded documents or scalars the list
    type is inferred from the inner field's converted type.

    Args:
        field: The MongoEngine list field instance.
        registry (Registry | None): Active type registry.
        executor (ExecutorEnum): Controls which resolver variant is attached.

    Returns:
        graphene.List or a ConnectionField if the inner type is a Relay Node.
    """
    base_type = convert_mongoengine_field(field.field, registry=registry, executor=executor)
    if isinstance(base_type, graphene.Field):
        if isinstance(field.field, mongoengine.GenericReferenceField):
            return graphene.List(
                base_type._type,
                description=get_field_description(field, registry),
                required=get_field_is_required(field, registry),
            )
        return graphene.List(
            base_type._type,
            description=get_field_description(field, registry),
            required=get_field_is_required(field, registry),
        )
    if isinstance(base_type, (graphene.Dynamic)):
        base_type = base_type.get_type()
        if base_type is None:
            return
        base_type = base_type._type

    if graphene.is_node(base_type):
        return base_type._meta.connection_field_class(base_type)

    # Non-relationship field
    relations = (mongoengine.ReferenceField, mongoengine.EmbeddedDocumentField)
    if not isinstance(base_type, (graphene.List, graphene.NonNull)) and not isinstance(
            field.field, relations
    ):
        base_type = type(base_type)

    return graphene.List(
        base_type,
        description=get_field_description(field, registry),
        required=get_field_is_required(field, registry),
    )


@convert_mongoengine_field.register(mongoengine.GenericEmbeddedDocumentField)
@convert_mongoengine_field.register(mongoengine.GenericReferenceField)
def convert_field_to_union(field, registry=None, executor: ExecutorEnum = ExecutorEnum.SYNC):
    """Convert GenericEmbeddedDocumentField / GenericReferenceField → graphene Union Field.

    Builds a dynamic graphene.Union type from the field's choices list,
    then wraps it in a graphene.Field with an appropriate resolver that
    identifies the concrete type at query time.

    Args:
        field: The MongoEngine generic field instance.
        registry (Registry | None): Active type registry.
        executor (ExecutorEnum): Controls which resolver variant is attached.

    Returns:
        graphene.Field wrapping the generated Union type, or None if
        none of the choices have been registered yet.
    """
    _types = []
    for choice in field.choices:
        if isinstance(field, mongoengine.GenericReferenceField):
            _field = mongoengine.ReferenceField(get_document(choice))
        elif isinstance(field, mongoengine.GenericEmbeddedDocumentField):
            _field = mongoengine.EmbeddedDocumentField(choice)

        _field = convert_mongoengine_field(_field, registry, executor=executor)
        _type = _field.get_type()
        if _type:
            _types.append(_type.type)
        else:
            # TODO: Register type auto-matically here.
            pass

    if len(_types) == 0:
        return None

    field_name = field.db_field
    if field_name is None:
        # Get db_field name from parent mongo_field
        for db_field_name, _mongo_parent_field in field.owner_document._fields.items():
            if hasattr(_mongo_parent_field, "field") and _mongo_parent_field.field == field:
                field_name = db_field_name
                break

    name = to_camel_case(
        "{}_{}_union_type".format(
            field._owner_document.__name__,
            field_name,
        )
    )
    Meta = type("Meta", (object,), {"types": tuple(_types)})
    _union = type(name, (graphene.Union,), {"Meta": Meta})

    if isinstance(field, mongoengine.GenericReferenceField):
        field_resolver = None
        required = False
        if field.db_field is not None:
            required = get_field_is_required(field, registry)
            resolver_function = getattr(
                registry.get_type_for_model(field.owner_document),
                "resolve_" + field.db_field,
                None,
            )
            if resolver_function and callable(resolver_function):
                field_resolver = resolver_function
        return graphene.Field(
            _union,
            resolver=field_resolver,
            description=get_field_description(field, registry),
            required=required,
        )

    return graphene.Field(_union)


@convert_mongoengine_field.register(mongoengine.EmbeddedDocumentField)
@convert_mongoengine_field.register(mongoengine.ReferenceField)
def convert_field_to_dynamic(field, registry=None, executor: ExecutorEnum = ExecutorEnum.SYNC):
    """Convert EmbeddedDocumentField / ReferenceField → graphene.Dynamic.

    Returns a graphene.Dynamic so that the target type is resolved lazily
    at schema build time, allowing forward references between types that are
    defined in any order.

    Args:
        field: The MongoEngine embedded or reference field instance.
        registry (Registry | None): Active type registry.
        executor (ExecutorEnum): Controls which resolver variant is attached.

    Returns:
        graphene.Dynamic: Evaluates to a graphene.Field once the target
        type is available in the registry.
    """
    model = field.document_type

    def dynamic_type():
        _type = registry.get_type_for_model(model)
        if not _type:
            return None
        if isinstance(field, mongoengine.EmbeddedDocumentField):
            return graphene.Field(
                _type,
                description=get_field_description(field, registry),
                required=get_field_is_required(field, registry),
            )
        field_resolver = None
        required = False
        if field.db_field is not None:
            required = get_field_is_required(field, registry)
            resolver_function = getattr(
                registry.get_type_for_model(field.owner_document),
                "resolve_" + field.db_field,
                None,
            )
            if resolver_function and callable(resolver_function):
                field_resolver = resolver_function
        return graphene.Field(
            _type,
            resolver=field_resolver,
            description=get_field_description(field, registry),
            required=required,
        )

    return graphene.Dynamic(dynamic_type)


@convert_mongoengine_field.register(mongoengine.EnumField)
def convert_field_to_enum(field, registry=None, executor: ExecutorEnum = ExecutorEnum.SYNC):
    """Convert EnumField → graphene.Field wrapping a graphene.Enum.

    Registers the Python enum class with the registry on first encounter so
    that the same graphene.Enum wrapper is reused for all fields sharing the
    same enum class.

    Args:
        field: The MongoEngine EnumField instance.
        registry (Registry): Active type registry (must not be None).
        executor (ExecutorEnum): Unused for scalar enum fields.

    Returns:
        graphene.Field: Wraps the registered graphene.Enum type.
    """
    if not registry.check_enum_already_exist(field._enum_cls):
        registry.register_enum(field._enum_cls)
    _type = registry.get_type_for_enum(field._enum_cls)
    return graphene.Field(
        _type,
        description=get_field_description(field, registry),
        required=get_field_is_required(field, registry),
    )
