import datetime as _datetime
from collections import OrderedDict
from functools import reduce

import bson
import graphene
import mongoengine
from bson import ObjectId
from graphene.relay import ConnectionField, is_node
from graphene.types.argument import to_arguments
from graphene.types.dynamic import Dynamic
from graphene.types.structures import Structure
from graphene.types.utils import get_type
from graphene.utils.str_converters import to_snake_case
from graphql import GraphQLResolveInfo
from graphql_relay import from_global_id

from .advanced_types import (
    AwareDateTimeScalar,
    FileFieldType,
    MultiPolygonFieldType,
    PointFieldInputType,
    PointFieldType,
    PolygonFieldType,
)
from .converter import MongoEngineConversionError, convert_mongoengine_field
from .registry import get_global_registry
from .utils import (
    ExecutorEnum,
    get_document,
    get_model_reference_fields,
    get_query_fields,
    get_related_field_filter_args,
    get_select_related_paths,
)

_UTC = _datetime.timezone.utc


def _to_utc(value):
    """Normalise a datetime (or list of datetimes) to UTC.

    Used by _hydrate_args to rewrite AwareDateTimeField filter values before
    they are passed to MongoEngine. Handles the in/nin/all list case as well as
    single values, and assumes UTC when the value has no tzinfo.
    """
    if isinstance(value, list):
        return [_to_utc(v) for v in value]
    if value.tzinfo is None:
        value = value.replace(tzinfo=_UTC)
    return value.astimezone(_UTC)


class BaseMongoengineConnectionField(ConnectionField):
    """Shared base class for sync and async MongoEngine connection fields.

    Provides all properties and helper methods that are identical between
    MongoengineConnectionField (sync)
    and AsyncMongoengineConnectionField
    (async). Subclasses must override executor and, optionally,
    _qs_accessor (async overrides it to return model.aobjects instead
    of model.objects).

    The get_queryset, default_resolver, chained_resolver, and
    connection_resolver methods are implemented in the concrete subclasses
    because they differ in whether they are async def and in how they call the
    queryset managers.
    """

    def __init__(self, type, *args, **kwargs):
        """Initialise the connection field, optionally accepting a custom get_queryset.

        Args:
            type: The graphene ObjectType (or its connection) this field resolves to.
            *args: Forwarded to ConnectionField.
            **kwargs: Forwarded to ConnectionField.
                Special key get_queryset (callable | None): When provided, called
                during resolution to supply or override the MongoEngine QuerySet.
                Must be callable; otherwise an AssertionError is raised.
        """
        get_queryset = kwargs.pop("get_queryset", None)
        if get_queryset:
            assert callable(get_queryset), (
                "Attribute `get_queryset` on {} must be callable.".format(self)
            )
        self._get_queryset = get_queryset
        super().__init__(type, *args, **kwargs)

    @property
    def executor(self) -> ExecutorEnum:
        """Return the executor variant (SYNC or ASYNC) for this field.

        Must be overridden by subclasses to return ExecutorEnum.SYNC or
        ExecutorEnum.ASYNC.

        Raises:
            NotImplementedError: If not overridden in a subclass.
        """
        raise NotImplementedError

    @property
    def node_type(self):
        """Return the graphene node type from the connection's _meta.node.

        Returns:
            type: The graphene ObjectType (e.g. ArticleType) backing the connection.
        """
        return self.type._meta.node

    @property
    def model(self):
        """Return the MongoEngine model class backing the node type.

        Returns:
            type: A MongoEngine Document subclass.
        """
        return self.node_type._meta.model

    @property
    def order_by(self):
        """Return the default ordering expression declared in the node type's Meta.

        Returns:
            str | None: MongoEngine ordering string (e.g. "-created_at"), or None.
        """
        return self.node_type._meta.order_by

    @property
    def required_fields(self):
        """Return the union of required_fields and only_fields from Meta.

        These fields are always fetched from MongoDB regardless of the GraphQL
        query selection, ensuring relationships and computed properties work correctly.

        Returns:
            tuple[str]: Deduplicated tuple of field names to always project.
        """
        return tuple(set(self.node_type._meta.required_fields + self.node_type._meta.only_fields))

    @property
    def registry(self):
        """Return the type registry associated with this field's node type.

        Falls back to the global sync registry if the node type has no explicit registry.

        Returns:
            Registry: The active type registry.
        """
        return getattr(self.node_type._meta, "registry", get_global_registry())

    @property
    def args(self):
        """Build the complete set of GraphQL arguments for this connection field.

        Merges field_args, advance_args, filter_args, and extended_args
        into a single argument map, then strips any field names listed in
        Meta.non_filter_fields and removes keys already present in _base_args
        (the built-in Relay pagination args: first, last, before, after).

        Returns:
            OrderedDict: Complete argument mapping passed to the generated GraphQL field.
        """
        _field_args = self.field_args
        _advance_args = self.advance_args
        _filter_args = self.filter_args
        _extended_args = self.extended_args
        if self._type._meta.non_filter_fields:
            for _field in self._type._meta.non_filter_fields:
                if _field in _field_args:
                    _field_args.pop(_field)
                if _field in _advance_args:
                    _advance_args.pop(_field)
                if _field in _filter_args:
                    _filter_args.pop(_field)
                if _field in _extended_args:
                    _filter_args.pop(_field)
        extra_args = dict(
            dict(dict(_field_args, **_advance_args), **_filter_args), **_extended_args
        )
        for key in list(self._base_args.keys()):
            extra_args.pop(key, None)
        return to_arguments(self._base_args or OrderedDict(), extra_args)

    @args.setter
    def args(self, args):
        """Store the base (Relay pagination) args before the extra field args are merged in.

        Args:
            args: The base argument mapping supplied by graphene's ConnectionField.
        """
        self._base_args = args

    def _field_args(self, items):
        """Filter *items* down to the subset of fields that are usable as query arguments.

        A field is excluded when it:
        - is backed by an SDL-annotated federation key (@key directive)
        - is a Python property on the model
        - converts to a ConnectionField or Dynamic
        - converts to a complex output type (FileFieldType, geo types, Union)
        - is a List whose element type is a Union or ObjectType
        - has a mismatching type between the graphene field and converter output

        Args:
            items: Iterable of (name, graphene_field) pairs (from self.fields.items()).

        Returns:
            dict[str, graphene scalar instance]: Filterable field names mapped to their
            scalar type instance (suitable for use as a GraphQL argument type).
        """

        def is_filterable(k):
            if hasattr(self.fields[k].type, "_sdl"):
                return False
            if not hasattr(self.model, k):
                return False
            else:
                field_ = self.fields[k]
                type_ = field_.type
                while hasattr(type_, "of_type"):
                    type_ = type_.of_type
                if hasattr(type_, "_sdl") and "@key" in type_._sdl:
                    return False
            if isinstance(getattr(self.model, k), property):
                return False
            try:
                converted = convert_mongoengine_field(
                    getattr(self.model, k), self.registry, self.executor
                )
            except MongoEngineConversionError:
                return False
            if isinstance(converted, (ConnectionField, Dynamic)):
                return False
            if callable(getattr(converted, "type", None)) and isinstance(
                converted.type(),
                (
                    FileFieldType,
                    PointFieldType,
                    MultiPolygonFieldType,
                    PolygonFieldType,
                    graphene.Union,
                ),
            ):
                return False
            if isinstance(converted, graphene.List):
                sub_type = getattr(converted, "_of_type", None)
                if hasattr(sub_type, "of_type"):
                    sub_type = sub_type.of_type
                if issubclass(sub_type, graphene.Union) or issubclass(
                    sub_type, graphene.ObjectType
                ):
                    return False
            if (
                hasattr(field_, "type")
                and hasattr(converted, "type")
                and converted.type != field_.type
            ):
                return False
            return True

        def get_filter_type(_type, field_name):
            if isinstance(_type, Structure):
                return get_filter_type(_type.of_type, field_name)

            if is_node(_type):
                # Allow federated node types to be added as filters
                # This case occurs when user defines the field's external type manually within
                # the AsyncMongoengineObjectType definition
                return convert_mongoengine_field(
                    getattr(self.model, field_name), self.registry, self.executor
                )

            return _type()

        return {
            field_name: field_type
            for field_name, gql_type in items
            if is_filterable(field_name)
            for field_type in [get_filter_type(gql_type.type, field_name)]
            if field_type is not None
        }

    @property
    def field_args(self):
        """Return filterable scalar arguments derived from the node type's fields.

        Delegates to _field_args over all fields declared on the graphene type.

        Returns:
            dict[str, graphene scalar instance]: Field-level filter arguments.
        """
        return self._field_args(self.fields.items())

    @property
    def filter_args(self):
        """Build filter arguments from the Meta.filter_fields declaration.

        filter_fields is a dict of {field_name: [lookup, ...]} (e.g.
        {"name": ["exact", "icontains"]}).  For each lookup a corresponding
        graphene.Argument is generated, using graphene.List for
        in / nin / all lookups and PointFieldInputType for geo
        near queries.

        Returns:
            dict[str, graphene.Argument]: Lookup-style filter argument mapping,
            keyed by "field__lookup" (e.g. "name__icontains").
        """
        filter_args = dict()
        if self._type._meta.filter_fields:
            for field, filter_collection in self._type._meta.filter_fields.items():
                for each in filter_collection:
                    field_type_str = str(self._type._meta.fields[field].type)
                    if field_type_str in ("PointFieldType", "PointFieldType!"):
                        if each == "max_distance":
                            filter_type = graphene.Int
                        else:
                            filter_type = PointFieldInputType
                    elif field_type_str in ("AwareDateTime", "AwareDateTime!"):
                        filter_type = AwareDateTimeScalar
                    else:
                        filter_type = getattr(
                            graphene,
                            field_type_str.replace("!", ""),
                        )
                    advanced_filter_types = {
                        "in": graphene.List(filter_type),
                        "nin": graphene.List(filter_type),
                        "all": graphene.List(filter_type),
                    }
                    filter_type = advanced_filter_types.get(each, filter_type)
                    filter_args[field + "__" + each] = graphene.Argument(type_=filter_type)
        return filter_args

    @property
    def advance_args(self):
        """Build advanced filter arguments for reference and geo fields.

        For PointField fields adds a PointFieldInputType argument.
        For ReferenceField / GenericReferenceField fields adds a graphene.ID
        argument so callers can filter by global ID.
        For other Dynamic fields, if the resolved type has an id field and
        is not an EmbeddedDocument, adds its ID type as an argument.

        Returns:
            dict[str, graphene argument]: Advanced argument mapping keyed by field name.
        """

        def get_advance_field(r, kv):
            field = kv[1]
            mongo_field = getattr(self.model, kv[0], None)
            if isinstance(mongo_field, mongoengine.PointField):
                r.update({kv[0]: graphene.Argument(PointFieldInputType)})
                return r
            if isinstance(
                mongo_field,
                (mongoengine.ReferenceField, mongoengine.GenericReferenceField),
            ):
                r.update({kv[0]: graphene.ID()})
                return r
            if isinstance(mongo_field, mongoengine.GenericReferenceField):
                r.update({kv[0]: graphene.ID()})
                return r
            if callable(getattr(field, "get_type", None)):
                _type = field.get_type()
                if _type:
                    node = (
                        _type.type._meta
                        if hasattr(_type.type, "_meta")
                        else _type.type._of_type._meta
                    )
                    if "id" in node.fields and not issubclass(
                        node.model, (mongoengine.EmbeddedDocument,)
                    ):
                        r.update({kv[0]: node.fields["id"]._type.of_type()})
            return r

        return reduce(get_advance_field, self.fields.items(), {})

    @property
    def extended_args(self):
        """Build extra graphene.ID arguments for federation-annotated fields.

        Fields whose graphene type carries an _sdl attribute (i.e. fields
        declared via graphene_federation) are exposed as ID arguments so
        they can still be used as filters.

        Returns:
            dict[str, graphene.ID]: Mapping of field name → graphene.ID() instance.
        """
        args = OrderedDict()
        for k, each in self.fields.items():
            if hasattr(each.type, "_sdl"):
                args.update({k: graphene.ID()})
        return args

    @property
    def fields(self):
        """Return the resolved _meta.fields dict of the node type.

        Forces lazy type resolution (get_type) before accessing metadata so
        that Dynamic / string-reference types are fully initialised.

        Returns:
            dict[str, graphene.Field]: All fields declared on the graphene type.
        """
        self._type = get_type(self._type)
        return self._type._meta.fields

    # ── helpers ──────────────────────────────────────────────────────────────

    def _hydrate_args(self, args: dict) -> None:
        """Hydrate reference and geo args in-place, converting GraphQL representations to MongoEngine objects.

        Performs three types of conversion:

        - ReferenceField args: Relay global ID strings are decoded via from_global_id
          and used to construct a lightweight document stub (DocumentClass(pk=...)).
        - GenericReferenceField args: The global ID is decoded to extract the type name
          and PK; the document class is looked up in the registry.
        - Geo __near args: The PointFieldInputType dict is converted to a coordinate
          list; a default __max_distance of 10,000 is added if not already present.
        - Plain id args: Decoded from global ID format and replaced in-place.

        Args:
            args (dict): Mutable argument dict to update in-place; keys are field names
                and values are the raw GraphQL argument values.
        """
        reference_fields = get_model_reference_fields(self.model)
        hydrated: dict = {}
        for arg_name, arg in args.copy().items():
            if arg_name in reference_fields and not isinstance(
                arg, mongoengine.base.TopLevelDocumentMetaclass
            ):
                try:
                    reference_obj = reference_fields[arg_name].document_type(
                        pk=from_global_id(arg)[1]
                    )
                except TypeError:
                    reference_obj = reference_fields[arg_name].document_type(pk=arg)
                hydrated[arg_name] = reference_obj
            elif arg_name in self.model._fields_ordered and isinstance(
                getattr(self.model, arg_name), mongoengine.fields.GenericReferenceField
            ):
                try:
                    reference_obj = get_document(
                        self.registry.get_type_for_model_string(from_global_id(arg)[0])
                    )(pk=from_global_id(arg)[1])
                except TypeError:
                    reference_obj = get_document(arg["_cls"])(pk=arg["_ref"].id)
                hydrated[arg_name] = reference_obj
            elif "__near" in arg_name and isinstance(
                getattr(self.model, arg_name.split("__")[0]), mongoengine.fields.PointField
            ):
                location = args.pop(arg_name, None)
                hydrated[arg_name] = location["coordinates"]
                if (arg_name.split("__")[0] + "__max_distance") not in args:
                    hydrated[arg_name.split("__")[0] + "__max_distance"] = 10000
            elif arg_name in self.model._fields_ordered and isinstance(
                getattr(self.model, arg_name), mongoengine.AwareDateTimeField
            ):
                # AwareDateTimeField stores {"utc": datetime, "tz": str}.
                # Rewrite bare field filter to compare against the utc subfield.
                hydrated[arg_name + "__utc"] = _to_utc(args.pop(arg_name))
            elif "__" in arg_name:
                # Handle operator suffixes e.g. start_time__gte, start_time__lte,
                # start_time__in (list), etc.
                field_name, _, op = arg_name.partition("__")
                if field_name in self.model._fields_ordered and isinstance(
                    getattr(self.model, field_name), mongoengine.AwareDateTimeField
                ):
                    value = args.pop(arg_name)
                    hydrated[field_name + "__utc__" + op] = _to_utc(value)
            elif arg_name == "id":
                hydrated["id"] = from_global_id(args.pop("id", None))[1]
        args.update(hydrated)

    def _qs_accessor(self, model):
        """Return the synchronous QuerySet manager for the given model.

        The async subclass overrides this to return model.aobjects so that
        the entire get_queryset implementation can live in the base class with
        only this single line differing between sync and async.

        Args:
            model: A MongoEngine Document subclass.

        Returns:
            mongoengine.QuerySet: The model.objects manager.
        """
        return model.objects

    def _apply_select_related(self, qs, model, info):
        """Apply select_related and sub-field filters to a QuerySet.

        Walks the current GraphQL query selection (via get_query_fields) to
        determine which reference fields are being queried.  For each, a
        select_related path is added and any filter arguments declared on the
        sub-field (e.g. articles(headline: "Hello")) are pushed into the QS
        via filter(articles__headline="Hello").

        Args:
            qs: The base MongoEngine QuerySet to augment.
            model: The MongoEngine Document class being queried.
            info: The GraphQL resolve info (GraphQLResolveInfo); when *info* is not
                a GraphQLResolveInfo instance (e.g. in tests) the step is skipped.

        Returns:
            QuerySet: The augmented QuerySet (may be the same object if no paths found).
        """
        queried_fields = get_query_fields(info) if isinstance(info, GraphQLResolveInfo) else {}
        related = get_select_related_paths(model, queried_fields)
        related_filter = (
            get_related_field_filter_args(info, model)
            if isinstance(info, GraphQLResolveInfo)
            else {}
        )
        if related:
            qs = qs.select_related(*related)
            for field_name, field_filter in related_filter.items():
                if field_name in related:
                    qs = qs.filter(**{f"{field_name}__{k}": v for k, v in field_filter.items()})
        return qs

    def _build_args_copy(self, args: dict) -> dict:
        """Build a filtered copy of *args* suitable for MongoDB count / filter queries.

        Strips keys that are not MongoEngine field names on this model, and converts
        reference field values to ObjectId and enum field values to their raw Python
        value so that MongoDB accepts them directly.

        Args:
            args (dict): The current resolver argument dict (not mutated).

        Returns:
            dict: A new dict containing only model-level field keys, with reference
            values decoded to ObjectId and enum values unwrapped.
        """
        args_copy = args.copy()
        for key in args.copy():
            if key not in self.model._fields_ordered:
                args_copy.pop(key)
            elif isinstance(
                getattr(self.model, key), mongoengine.fields.ReferenceField
            ) or isinstance(getattr(self.model, key), mongoengine.fields.GenericReferenceField):
                if not isinstance(args_copy[key], ObjectId):
                    _from_global_id = from_global_id(args_copy[key])[1]
                    args_copy[key] = (
                        ObjectId(_from_global_id)
                        if bson.objectid.ObjectId.is_valid(_from_global_id)
                        else _from_global_id
                    )
            elif isinstance(getattr(self.model, key), mongoengine.fields.EnumField):
                if getattr(args_copy[key], "value", None):
                    args_copy[key] = args_copy[key].value
        return args_copy

    def _prepare_resolver_inputs(self, _root, info, args: dict, resolved):
        """Pre-process _root to populate args['pk__in'] or a pre-loaded resolved list.

        When a parent document is present (_root is not None), inspects the
        field value on the parent to determine the resolution strategy:

        - If the parent does not have _fields_ordered (non-Document root), treats
          the field value as a plain Python list and sets args["pk__in"] to its IDs.
        - If the field is a list of already-loaded Document instances (pre-fetched
          by select_related), populates resolved directly and clears non-id
          args to avoid a redundant DB query.
        - Otherwise, sets args["pk__in"] from the raw reference list.

        Args:
            _root: The parent resolver root object, or None for top-level queries.
            info: GraphQL resolve info object (used to derive the field name).
            args (dict): Mutable argument dict, updated in-place with pk__in if needed.
            resolved: Pre-loaded iterable of documents, or None.

        Returns:
            tuple[str, list | None]: (field_name, resolved) where field_name is
            the snake_case field name on the parent, and resolved is either the
            pre-loaded list or None if a DB query is still required.
        """
        field_name = to_snake_case(info.field_name) if _root is not None else ""
        if _root is not None and not resolved:
            if not hasattr(_root, "_fields_ordered"):
                if isinstance(getattr(_root, field_name, []), list):
                    args["pk__in"] = [r.id for r in getattr(_root, field_name, [])]
            elif field_name in _root._fields_ordered and not (
                isinstance(_root._fields[field_name].field, mongoengine.EmbeddedDocumentField)
                or isinstance(
                    _root._fields[field_name].field,
                    mongoengine.GenericEmbeddedDocumentField,
                )
            ):
                raw = getattr(_root, field_name, [])
                if raw is not None:
                    first_item = next(iter(raw), None)
                    if isinstance(first_item, mongoengine.Document):
                        # Pre-loaded by select_related; filter already pushed into
                        # the $lookup sub-pipeline via filter(**related_filter).
                        resolved = list(raw)
                        for k in [k for k in args if k != "id"]:
                            args.pop(k)
                    else:
                        args["pk__in"] = [r.id for r in raw]
        return field_name, resolved

    def _collect_required_fields(self, info) -> list:
        """Collect the set of MongoEngine fields that must be fetched for this query.

        Combines:
        1. required_fields from the node type's Meta (always fetched).
        2. All snake_case field names from the current GraphQL query selection
           that map to actual MongoEngine fields on the model.

        Args:
            info: GraphQL resolve info object; passed to get_query_fields.

        Returns:
            list[str]: Field names to pass to .only(...) on the QuerySet.
        """
        required_fields = [f for f in self.required_fields if f in self.model._fields_ordered]
        required_fields += [
            to_snake_case(f)
            for f in get_query_fields(info)
            if to_snake_case(f) in self.model._fields_ordered
        ]
        return required_fields

    def _transform_qs_args(self, args: dict, args_copy: dict) -> dict:
        """Re-map a resolved QuerySet's _query dict into graphene-mongo style args.

        When a custom resolver returns a QuerySet, its internal _query dict
        uses MongoDB wire format (dotted paths, $lte / $gte operators, etc.).
        This method converts those entries into the __-separated format that
        graphene-mongo passes to default_resolver.

        Specifically:
        - Keys with . are rewritten to use __ separators.
        - The special _id key (with $in / $lte etc.) is rewritten to pk__in etc.
        - Standard comparison operators ($lte, $gte, $ne, $in) inside
          a field value dict are appended as field__lte, field__gte, etc.
        - Keys not in the model's field list or the Relay args / filter args are stripped.

        Args:
            args (dict): The merged _query dict (mutated by this method for operator lookups).
            args_copy (dict): A pre-made copy of *args* that is returned as the result.

        Returns:
            dict: The transformed args_copy ready for default_resolver.
        """
        for arg_name, arg in args.copy().items():
            if "." in arg_name or arg_name not in self.model._fields_ordered + (
                "first",
                "last",
                "before",
                "after",
            ) + tuple(self.filter_args.keys()):
                args_copy.pop(arg_name, None)
                if arg_name == "_id" and isinstance(arg, dict):
                    operation = list(arg.keys())[0]
                    args_copy["pk" + operation.replace("$", "__")] = arg[operation]
                if not isinstance(arg, ObjectId) and "." in arg_name:
                    if isinstance(arg, dict):
                        operation = list(arg.keys())[0]
                        args_copy[arg_name.replace(".", "__") + operation.replace("$", "__")] = arg[
                            operation
                        ]
                    else:
                        args_copy[arg_name.replace(".", "__")] = arg
                elif "." in arg_name and isinstance(arg, ObjectId):
                    args_copy[arg_name.replace(".", "__")] = arg
            else:
                operations = ["$lte", "$gte", "$ne", "$in"]
                if isinstance(arg, dict) and any(op in arg for op in operations):
                    operation = list(arg.keys())[0]
                    args_copy[arg_name + operation.replace("$", "__")] = arg[operation]
                    del args_copy[arg_name]
        return args_copy
