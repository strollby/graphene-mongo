from __future__ import absolute_import

from collections import OrderedDict
from functools import reduce

import bson
import graphene
import mongoengine
from bson import ObjectId
from graphene.relay import ConnectionField
from graphene.types.argument import to_arguments
from graphene.types.dynamic import Dynamic
from graphene.types.structures import Structure
from graphene.types.utils import get_type
from graphene.utils.str_converters import to_snake_case
from graphql import GraphQLResolveInfo
from graphql_relay import from_global_id

from .advanced_types import (
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


class BaseMongoengineConnectionField(ConnectionField):
    def __init__(self, type, *args, **kwargs):
        get_queryset = kwargs.pop("get_queryset", None)
        if get_queryset:
            assert callable(get_queryset), (
                "Attribute `get_queryset` on {} must be callable.".format(self)
            )
        self._get_queryset = get_queryset
        super().__init__(type, *args, **kwargs)

    @property
    def executor(self) -> ExecutorEnum:
        raise NotImplementedError

    @property
    def node_type(self):
        return self.type._meta.node

    @property
    def model(self):
        return self.node_type._meta.model

    @property
    def order_by(self):
        return self.node_type._meta.order_by

    @property
    def required_fields(self):
        return tuple(set(self.node_type._meta.required_fields + self.node_type._meta.only_fields))

    @property
    def registry(self):
        return getattr(self.node_type._meta, "registry", get_global_registry())

    @property
    def args(self):
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
        self._base_args = args

    def _field_args(self, items):
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
                    graphene.Union,
                    PolygonFieldType,
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

        def get_filter_type(_type):
            if isinstance(_type, Structure):
                return get_filter_type(_type.of_type)
            return _type()

        return {k: get_filter_type(v.type) for k, v in items if is_filterable(k)}

    @property
    def field_args(self):
        return self._field_args(self.fields.items())

    @property
    def filter_args(self):
        filter_args = dict()
        if self._type._meta.filter_fields:
            for field, filter_collection in self._type._meta.filter_fields.items():
                for each in filter_collection:
                    if str(self._type._meta.fields[field].type) in (
                        "PointFieldType",
                        "PointFieldType!",
                    ):
                        if each == "max_distance":
                            filter_type = graphene.Int
                        else:
                            filter_type = PointFieldInputType
                    else:
                        filter_type = getattr(
                            graphene,
                            str(self._type._meta.fields[field].type).replace("!", ""),
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
        args = OrderedDict()
        for k, each in self.fields.items():
            if hasattr(each.type, "_sdl"):
                args.update({k: graphene.ID()})
        return args

    @property
    def fields(self):
        self._type = get_type(self._type)
        return self._type._meta.fields

    # ── helpers ──────────────────────────────────────────────────────────────

    def _hydrate_args(self, args: dict) -> None:
        """Hydrate reference/geo args in-place (global IDs → objects, coordinates)."""
        reference_fields = get_model_reference_fields(self.model)
        hydrated: dict = {}
        for arg_name, arg in args.copy().items():
            if arg_name in reference_fields and not isinstance(
                arg, mongoengine.base.metaclasses.TopLevelDocumentMetaclass
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
            elif arg_name == "id":
                hydrated["id"] = from_global_id(args.pop("id", None))[1]
        args.update(hydrated)

    def _qs_accessor(self, model):
        """Return the QuerySet manager for this executor. Overridden in async."""
        return model.objects

    def _apply_select_related(self, qs, model, info):
        """Apply select_related and related-field filters to a queryset."""
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
                    qs = qs.filter(
                        **{f"{field_name}__{k}": v for k, v in field_filter.items()}
                    )
        return qs

    def _build_args_copy(self, args: dict) -> dict:
        """Build a filtered args copy for count queries, normalising ObjectIds."""
        args_copy = args.copy()
        for key in args.copy():
            if key not in self.model._fields_ordered:
                args_copy.pop(key)
            elif isinstance(
                getattr(self.model, key), mongoengine.fields.ReferenceField
            ) or isinstance(
                getattr(self.model, key), mongoengine.fields.GenericReferenceField
            ):
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
        """
        Pre-process _root to set args['pk__in'] or populate a pre-loaded resolved list.
        Returns (field_name, resolved).
        """
        field_name = to_snake_case(info.field_name) if _root is not None else ""
        if _root is not None and not resolved:
            if not hasattr(_root, "_fields_ordered"):
                if isinstance(getattr(_root, field_name, []), list):
                    args["pk__in"] = [r.id for r in getattr(_root, field_name, [])]
            elif field_name in _root._fields_ordered and not (
                isinstance(
                    _root._fields[field_name].field, mongoengine.EmbeddedDocumentField
                )
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
        """Collect required fields from meta and the current query selection."""
        required_fields = [
            f for f in self.required_fields if f in self.model._fields_ordered
        ]
        required_fields += [
            to_snake_case(f)
            for f in get_query_fields(info)
            if to_snake_case(f) in self.model._fields_ordered
        ]
        return required_fields

    def _transform_qs_args(self, args: dict, args_copy: dict) -> dict:
        """Re-map a resolved QuerySet's _query dict into graphene-mongo style args."""
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
                        args_copy[
                            arg_name.replace(".", "__") + operation.replace("$", "__")
                        ] = arg[operation]
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
