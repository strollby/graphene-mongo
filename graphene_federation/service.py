import re

from graphene import ObjectType, String, Field
from graphene.utils.str_converters import to_camel_case

from graphene_federation.extend import extended_types
from .entity import custom_entities


def _mark_external(entity_name, entity, schema, auto_camelcase):
    for field_name in dir(entity):
        field = getattr(entity, field_name, None)
        if field is not None and getattr(field, '_external', False):
            # todo write tests on regexp
            field_name = to_camel_case(field_name) if auto_camelcase else field_name
            pattern = re.compile(
                r"(\s%s\s[^\{]*\{[^\}]*\s%s[\s]*:[\s]*[^\s]+)(\s)" % (
                    entity_name, field_name))
            schema = pattern.sub(r'\g<1> @external ', schema)

    return schema


def get_sdl(schema, custom_entities):
    string_schema = str(schema)
    string_schema = string_schema.replace("\n", " ")

    regex = r"schema \{(\w|\!|\s|\:)*\}"
    pattern = re.compile(regex)
    string_schema = pattern.sub(" ", string_schema)

    for entity_name, entity in custom_entities.items():
        type_def_re = r"(type %s [^\{]*)" % entity_name
        repl_str = r"\1 %s " % entity._sdl
        pattern = re.compile(type_def_re)
        string_schema = pattern.sub(repl_str, string_schema)

    for entity_name, entity in extended_types.items():
        string_schema = _mark_external(entity_name, entity, string_schema, schema.auto_camelcase)

        type_def_re = r"type %s ([^\{]*)" % entity_name
        type_def = r"type %s " % entity_name
        repl_str = r"extend %s \1" % type_def
        pattern = re.compile(type_def_re)

        string_schema = pattern.sub(repl_str, string_schema)

    return string_schema


def get_service_query(schema):
    sdl_str = get_sdl(schema, custom_entities)

    class _Service(ObjectType):
        sdl = String()

        def resolve_sdl(parent, _):
            return sdl_str

    class ServiceQuery(ObjectType):
        _service = Field(_Service, name="_service")

        def resolve__service(parent, info):
            return _Service()

    return ServiceQuery
