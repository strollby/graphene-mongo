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
    """Convert MongoEngine model fields to graphene field instances.

    Iterates over the model's fields in alphabetical order (from
    get_model_fields), applying the
    only_fields / exclude_fields filters, and delegates each field to
    convert_mongoengine_field.

    Self-referential ListField entries (a list whose element type is the
    owning model) are returned separately so they can be registered in a second
    pass after the owning graphene type exists in the registry.

    Args:
        model: MongoEngine Document or EmbeddedDocument class.
        registry (Registry): Active type registry.
        only_fields (tuple[str]): Whitelist of field names to include;
            an empty tuple means *all* fields are included.
        exclude_fields (tuple[str]): Field names to unconditionally skip.
        non_required_fields (tuple[str]): Field names whose required flag
            is forced to False in the generated graphene field.
        executor (ExecutorEnum): SYNC or ASYNC — controls which resolver
            variant is attached to relationship fields.

    Returns:
        tuple[dict, dict]:
            (converted_fields, self_referenced)

            - *converted_fields*: {name: graphene_field} for all immediately
              usable fields.
            - *self_referenced*: {name: mongoengine_field} for ListField
              entries that reference the owning model (resolved in a second pass
              by construct_self_referenced_fields).
    """
    _model_fields = get_model_fields(model)
    fields = dict()
    self_referenced = dict()
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
            if name in non_required_fields:
                if isinstance(converted, graphene.Dynamic):
                    _orig_fn = converted.type

                    def _make_optional(fn):
                        def _thunk():
                            result = fn()
                            if result is not None and hasattr(result, "kwargs"):
                                result.kwargs["required"] = False
                            return result

                        return _thunk

                    converted = graphene.Dynamic(_make_optional(_orig_fn))
                elif "required" in converted.kwargs:
                    converted.kwargs["required"] = False
        fields[name] = converted

    return fields, self_referenced


def construct_self_referenced_fields(self_referenced, registry, executor=ExecutorEnum.SYNC):
    """Convert self-referential ListFields after the owning type is registered.

    Called in a second pass because the graphene type must exist in the registry
    before its own circular reference field can be resolved by the converter.

    Args:
        self_referenced (dict): {name: mongoengine_field} mapping returned
            by construct_fields for self-referential ListFields.
        registry (Registry): Active type registry (owning type already registered).
        executor (ExecutorEnum): SYNC or ASYNC.

    Returns:
        dict: {name: graphene_field} for the successfully converted fields.
    """
    fields = dict()
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
    """Factory that produces a MongoEngine-aware graphene ObjectType base class.

    The returned class (GrapheneMongoengineGenericType) is the shared ancestor
    for both MongoengineObjectType (sync) and AsyncMongoengineObjectType
    (async). Callers inject the executor, registry factories, and default
    connection field class so that the same factory body serves both variants
    without duplication.

    The produced class exposes:

    - __init_subclass_with_meta__ — wires up model, registry,
      fields, and connection when a user declares
      class MyType(MongoengineObjectType): class Meta: model = Article.
    - rescan_fields() — re-converts fields that were unresolvable at first
      registration (e.g. forward references to types defined later).
    - is_type_of() — used by graphene to resolve abstract / union types.
    - resolve_id() — returns str(self.id) for the Relay global ID.

    get_node is **not** defined here; it differs between sync (plain method)
    and async (async def), and is injected by the caller via classmethod
    attribute assignment after this factory returns.

    Args:
        object_type: graphene base class to inherit from
            (ObjectType, Interface, or InputObjectType).
        option_type: Matching options class
            (ObjectTypeOptions, InterfaceOptions, etc.).
        executor (ExecutorEnum): SYNC or ASYNC.
        global_registry_factory (callable): Zero-argument callable that returns
            the singleton Registry for regular object types.
        inputs_registry_factory (callable): Zero-argument callable that returns
            the singleton Registry for InputObjectType registrations.
        default_connection_field_class (type): ConnectionField subclass used
            when Meta.connection_field_class is not specified.

    Returns:
        tuple[type, type]:
            (GrapheneMongoengineGenericType, MongoengineGenericObjectTypeOptions)
    """

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
            """Wire up a user-defined MongoengineObjectType subclass.

            Called automatically by Python when the user writes
            class MyType(MongoengineObjectType): class Meta: model = Article.

            Args:
                model: MongoEngine Document or EmbeddedDocument class
                    that backs this graphene type. Required.
                registry (Registry | None): Explicit registry to use; when
                    omitted the appropriate singleton is chosen automatically.
                skip_registry (bool): If True, the type is not registered
                    after creation (useful for abstract base types).
                only_fields (tuple[str]): Whitelist of model field names to expose.
                required_fields (tuple[str]): Fields always fetched from MongoDB
                    regardless of the GraphQL query selection.
                exclude_fields (tuple[str]): Model field names to hide.
                non_required_fields (tuple[str]): Fields whose graphene required
                    flag is forced to False.
                filter_fields (dict | None): Lookup-style filter declarations,
                    e.g. {"name": ["exact", "icontains"]}.
                non_filter_fields (tuple[str]): Fields excluded from auto-generated
                    filter arguments.
                connection (type | None): Explicit Relay connection class.
                connection_class (type | None): Used to auto-create the connection.
                use_connection (bool | None): Override connection auto-detection.
                connection_field_class (type | None): ConnectionField subclass
                    for this type's connection field.
                interfaces (tuple): graphene interfaces implemented by this type.
                _meta: Pre-built options object; raises if wrong type.
                order_by (str | None): Default MongoEngine ordering expression.
                **options: Forwarded to the graphene base class.

            Raises:
                AssertionError: On invalid model, registry, connection, or _meta.
            """
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
                    "_meta must be an instance of MongoengineGenericObjectTypeOptions, received {}"
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
            """Re-convert model fields that could not be resolved at first registration.

            Useful when types are defined in any order and some fields reference
            types that were not yet in the registry during the initial pass.
            Only adds newly resolvable fields — existing fields are not replaced.
            Self-referenced fields are intentionally excluded (they cannot change).
            """
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
            """Determine whether *root* is an instance of this graphene type.

            Used by graphene when resolving abstract types and union members.
            Accepts GridFSProxy objects (FileField values) as a special case.

            Args:
                root: The resolved Python object to check.
                info (GraphQLResolveInfo): GraphQL resolver context.

            Returns:
                bool: True if *root* is compatible with this type.
            """
            if isinstance(root, cls):
                return True
            if isinstance(root, mongoengine.GridFSProxy):
                return True
            if not is_valid_mongoengine_model(type(root)):
                return False
            return isinstance(root, cls._meta.model)

        def resolve_id(self, info):
            """Return the document's primary key as a string for the Relay id field.

            Returns:
                str: str(self.id)
            """
            return str(self.id)

    return GrapheneMongoengineGenericType, MongoengineGenericObjectTypeOptions
