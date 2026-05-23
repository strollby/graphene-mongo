from collections import OrderedDict

import graphene
import mongoengine
from graphene.relay import Connection, Node
from graphene.types.inputobjecttype import InputObjectType
from graphene.types.utils import yank_fields_from_attrs

from .converter import convert_mongoengine_field
from .registry import Registry
from .utils import ExecutorEnum, get_model_fields, is_valid_mongoengine_model


def construct_fields(
    model,
    registry,
    only_fields,
    exclude_fields,
    non_required_fields,
    executor: ExecutorEnum = ExecutorEnum.SYNC,
):
    _model_fields = get_model_fields(model)
    fields = OrderedDict()
    self_referenced = OrderedDict()
    for name, field in _model_fields.items():
        is_not_in_only = only_fields and name not in only_fields
        is_excluded = name in exclude_fields
        if is_not_in_only or is_excluded:
            continue
        if isinstance(field, mongoengine.ListField):
            if not field.field:
                continue
            document_type_obj = field.field.__dict__.get("document_type_obj", None)
            if (
                document_type_obj == model._class_name
                or isinstance(document_type_obj, model)
                or document_type_obj == model
            ):
                self_referenced[name] = field
                continue
        converted = convert_mongoengine_field(field, registry, executor)
        if not converted:
            continue
        else:
            if name in non_required_fields and "required" in converted.kwargs:
                converted.kwargs["required"] = False
        fields[name] = converted

    return fields, self_referenced


def construct_self_referenced_fields(self_referenced, registry, executor=ExecutorEnum.SYNC):
    fields = OrderedDict()
    for name, field in self_referenced.items():
        converted = convert_mongoengine_field(field, registry, executor)
        if not converted:
            continue
        fields[name] = converted
    return fields


def create_graphene_generic_class(
    object_type,
    option_type,
    *,
    executor,
    global_registry_factory,
    inputs_registry_factory,
    default_connection_field_class,
):
    class MongoengineGenericObjectTypeOptions(option_type):
        model = None
        registry = None  # type: Registry
        connection = None
        filter_fields = ()
        non_required_fields = ()
        order_by = None

    class GrapheneMongoengineGenericType(object_type):
        @classmethod
        def __init_subclass_with_meta__(
            cls,
            model=None,
            registry=None,
            skip_registry=False,
            only_fields=(),
            required_fields=(),
            exclude_fields=(),
            non_required_fields=(),
            filter_fields=None,
            non_filter_fields=(),
            connection=None,
            connection_class=None,
            use_connection=None,
            connection_field_class=None,
            interfaces=(),
            _meta=None,
            order_by=None,
            **options,
        ):
            assert is_valid_mongoengine_model(model), (
                "The attribute model in {}.Meta must be a valid Mongoengine Model. "
                'Received "{}" instead.'
            ).format(cls.__name__, type(model))

            if not registry:
                if issubclass(cls, InputObjectType):
                    registry = inputs_registry_factory()
                else:
                    registry = global_registry_factory()

            assert isinstance(registry, Registry), (
                "The attribute registry in {}.Meta needs to be an instance of "
                'Registry({}), received "{}".'
            ).format(object_type, cls.__name__, registry)

            converted_fields, self_referenced = construct_fields(
                model, registry, only_fields, exclude_fields, non_required_fields, executor
            )
            mongoengine_fields = yank_fields_from_attrs(converted_fields, _as=graphene.Field)
            if use_connection is None and interfaces:
                use_connection = any((issubclass(interface, Node) for interface in interfaces))

            if use_connection and not connection:
                if not connection_class:
                    connection_class = Connection
                connection = connection_class.create_type(
                    "{}Connection".format(options.get("name") or cls.__name__), node=cls
                )

            if connection is not None:
                assert issubclass(connection, Connection), (
                    "The attribute connection in {}.Meta must be of type Connection. "
                    'Received "{}" instead.'
                ).format(cls.__name__, type(connection))

            if connection_field_class is not None:
                assert issubclass(connection_field_class, graphene.ConnectionField), (
                    "The attribute connection_field_class in {}.Meta must be of type "
                    'graphene.ConnectionField. Received "{}" instead.'
                ).format(cls.__name__, type(connection_field_class))
            else:
                connection_field_class = default_connection_field_class

            if _meta:
                assert isinstance(_meta, MongoengineGenericObjectTypeOptions), (
                    "_meta must be an instance of MongoengineGenericObjectTypeOptions, "
                    "received {}"
                ).format(_meta.__class__)
            else:
                _meta = MongoengineGenericObjectTypeOptions(option_type)

            _meta.model = model
            _meta.registry = registry
            _meta.fields = mongoengine_fields
            _meta.filter_fields = filter_fields
            _meta.non_filter_fields = non_filter_fields
            _meta.connection = connection
            _meta.connection_field_class = connection_field_class
            _meta.only_fields = only_fields
            _meta.required_fields = required_fields
            _meta.exclude_fields = exclude_fields
            _meta.non_required_fields = non_required_fields
            _meta.order_by = order_by

            super(GrapheneMongoengineGenericType, cls).__init_subclass_with_meta__(
                _meta=_meta, interfaces=interfaces, **options
            )

            if not skip_registry:
                registry.register(cls)
                converted_fields = construct_self_referenced_fields(
                    self_referenced, registry, executor
                )
                if converted_fields:
                    mongoengine_fields = yank_fields_from_attrs(
                        converted_fields, _as=graphene.Field
                    )
                    cls._meta.fields.update(mongoengine_fields)
                    registry.register(cls)

        @classmethod
        def rescan_fields(cls):
            """Attempts to rescan fields and will insert any not converted initially"""
            converted_fields, _ = construct_fields(
                cls._meta.model,
                cls._meta.registry,
                cls._meta.only_fields,
                cls._meta.exclude_fields,
                cls._meta.non_required_fields,
                executor,
            )
            mongoengine_fields = yank_fields_from_attrs(converted_fields, _as=graphene.Field)
            for field in mongoengine_fields:
                if field not in cls._meta.fields:
                    cls._meta.fields.update({field: mongoengine_fields[field]})

        @classmethod
        def is_type_of(cls, root, info):
            if isinstance(root, cls):
                return True
            if isinstance(root, mongoengine.GridFSProxy):
                return True
            if not is_valid_mongoengine_model(type(root)):
                raise Exception(('Received incompatible instance "{}".').format(root))
            return isinstance(root, cls._meta.model)

        def resolve_id(self, info):
            return str(self.id)

    return GrapheneMongoengineGenericType, MongoengineGenericObjectTypeOptions
