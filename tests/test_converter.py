import graphene
import mongoengine

from graphene_mongo import advanced_types
from graphene_mongo.base.converter import convert_mongoengine_field


def assert_conversion(mongoengine_field, graphene_field, *args, **kwargs):
    field = mongoengine_field(*args, **kwargs)
    graphene_type = convert_mongoengine_field(field)
    assert isinstance(graphene_type, graphene_field)
    field = graphene_type.Field()
    return field


def test_should_unknown_mongoengine_field_raise_exception():
    from pytest import raises

    with raises(Exception) as excinfo:
        convert_mongoengine_field(None)
    assert "Don't know how to convert the MongoEngine field" in str(excinfo)


def test_should_email_convert_string():
    assert_conversion(mongoengine.EmailField, graphene.String)


def test_should_string_convert_string():
    assert_conversion(mongoengine.StringField, graphene.String)


def test_should_url_convert_string():
    assert_conversion(mongoengine.URLField, graphene.String)


def test_should_uuid_convert_id():
    assert_conversion(mongoengine.UUIDField, graphene.ID)


def test_sould_int_convert_int():
    assert_conversion(mongoengine.IntField, graphene.Int)


def test_sould_sequence_convert_field():
    assert_conversion(mongoengine.SequenceField, graphene.Int)


def test_should_object_id_convert_id():
    assert_conversion(mongoengine.ObjectIdField, graphene.ID)


def test_should_boolean_convert_boolean():
    assert_conversion(mongoengine.BooleanField, graphene.Boolean)


def test_should_decimal_convert_decimal():
    assert_conversion(mongoengine.DecimalField, graphene.Decimal)


def test_should_float_convert_float():
    assert_conversion(mongoengine.FloatField, graphene.Float)


def test_should_decimal128_convert_decimal():
    assert_conversion(mongoengine.Decimal128Field, graphene.Decimal)


def test_should_datetime_convert_datetime():
    assert_conversion(mongoengine.DateTimeField, graphene.DateTime)


def test_should_dict_convert_json():
    assert_conversion(mongoengine.DictField, graphene.JSONString)


def test_should_map_convert_json():
    assert_conversion(mongoengine.MapField, graphene.JSONString, field=mongoengine.StringField())


def test_should_point_convert_field():
    graphene_type = convert_mongoengine_field(mongoengine.PointField())
    assert isinstance(graphene_type, graphene.Field)
    assert graphene_type.type == advanced_types.PointFieldType
    assert isinstance(graphene_type.type.type, graphene.String)
    assert isinstance(graphene_type.type.coordinates, graphene.List)


def test_should_polygon_covert_field():
    graphene_type = convert_mongoengine_field(mongoengine.PolygonField())
    assert isinstance(graphene_type, graphene.Field)
    assert graphene_type.type == advanced_types.PolygonFieldType
    assert isinstance(graphene_type.type.type, graphene.String)
    assert isinstance(graphene_type.type.coordinates, graphene.List)


def test_should_multipolygon_convert_field():
    graphene_type = convert_mongoengine_field(mongoengine.MultiPolygonField())
    assert isinstance(graphene_type, graphene.Field)
    assert graphene_type.type == advanced_types.MultiPolygonFieldType
    assert isinstance(graphene_type.type.type, graphene.String)
    assert isinstance(graphene_type.type.coordinates, graphene.List)


def test_should_file_convert_field():
    graphene_type = convert_mongoengine_field(mongoengine.FileField())
    assert isinstance(graphene_type, graphene.Field)
    assert graphene_type.type == advanced_types.FileFieldType


def test_should_zoned_datetime_convert_field():
    graphene_type = convert_mongoengine_field(mongoengine.AwareDateTimeField())
    assert isinstance(graphene_type, graphene.Field)
    assert graphene_type.type == advanced_types.ZonedDateTimeType
    assert isinstance(graphene_type.type.utc, graphene.DateTime)
    assert isinstance(graphene_type.type.tz, graphene.String)


def test_should_field_convert_list():
    assert_conversion(mongoengine.ListField, graphene.List, field=mongoengine.StringField())


def test_should_geo_convert_list():
    assert_conversion(mongoengine.GeoPointField, graphene.List, field=mongoengine.FloatField())