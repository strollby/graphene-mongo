import base64
import datetime
import re

import graphene
from graphene_federation import shareable
from graphql.error import GraphQLError
from graphql.language.ast import StringValueNode
from graphql.language.printer import print_ast

try:
    from datetime import UTC
except ImportError:
    UTC = datetime.timezone.utc

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


@shareable  # Support Graphene Federation v2
class FileFieldType(graphene.ObjectType):
    """GraphQL ObjectType representing a MongoEngine FileField (GridFS blob).

    Exposes GridFS metadata and the raw file data encoded as a base64 string.

    Fields:
        content_type (String): MIME type of the stored file.
        md5 (String): MD5 checksum of the file contents.
        chunk_size (Int): GridFS chunk size in bytes.
        length (Int): Total file size in bytes.
        data (String): Base64-encoded raw file contents.
    """

    content_type = graphene.String()
    md5 = graphene.String()
    chunk_size = graphene.Int()
    length = graphene.Int()
    data = graphene.String()

    @classmethod
    def _resolve_fs_field(cls, field, name, default_value=None):
        """Fetch a named attribute from the GridFS proxy attached to *field*.

        Args:
            field: The graphene field instance; must carry instance and
                key attributes pointing to the parent document and field name.
            name (str): Name of the GridFS proxy attribute to read.
            default_value: Value returned when the attribute is absent on the proxy.

        Returns:
            The attribute value, or *default_value* if not present.
        """
        v = getattr(field.instance, field.key)
        return getattr(v, name, default_value)

    def resolve_content_type(self, info):
        """Resolve the MIME type of the stored file."""
        return FileFieldType._resolve_fs_field(self, "content_type")

    def resolve_md5(self, info):
        """Resolve the MD5 checksum of the stored file."""
        return FileFieldType._resolve_fs_field(self, "md5")

    def resolve_chunk_size(self, info):
        """Resolve the GridFS chunk size (defaults to 0 if unavailable)."""
        return FileFieldType._resolve_fs_field(self, "chunk_size", 0)

    def resolve_length(self, info):
        """Resolve the total file size in bytes (defaults to 0 if unavailable)."""
        return FileFieldType._resolve_fs_field(self, "length", 0)

    def resolve_data(self, info):
        """Read the raw file bytes from GridFS and return them base64-encoded.

        Returns:
            str | None: UTF-8 base64 string, or None if the file is empty.
        """
        v = getattr(self.instance, self.key)
        data = v.read()
        if data is not None:
            return base64.b64encode(data).decode("utf-8")
        return None


@shareable  # Support Graphene Federation v2
class _CoordinatesTypeField(graphene.ObjectType):
    """Internal base ObjectType for GeoJSON geometry types.

    Provides the type string field (e.g. "Point") shared by all
    GeoJSON geometry shapes. Subclasses add the appropriate coordinates
    field for their specific geometry.
    """

    type = graphene.String()

    def resolve_type(self, info):
        """Return the GeoJSON geometry type string stored in the raw dict."""
        return self["type"]

    def resolve_coordinates(self, info):
        """Return the raw coordinates from the GeoJSON dict."""
        return self["coordinates"]


class PointFieldType(_CoordinatesTypeField):
    """GraphQL ObjectType for a MongoEngine PointField (GeoJSON Point).

    Fields:
        type (String): Always "Point".
        coordinates (List[Float]): [longitude, latitude].
    """

    coordinates = graphene.List(graphene.Float)


class PointFieldInputType(graphene.InputObjectType):
    """GraphQL InputObjectType for filtering or mutating a MongoEngine PointField.

    Used as an argument type when querying by geographic point.

    Fields:
        type (String): GeoJSON geometry type; defaults to "Point".
        coordinates (List[Float]): Required [longitude, latitude] pair.
    """

    type = graphene.String(default_value="Point")
    coordinates = graphene.List(graphene.Float, required=True)


class PolygonFieldType(_CoordinatesTypeField):
    """GraphQL ObjectType for a MongoEngine PolygonField (GeoJSON Polygon).

    Fields:
        type (String): Always "Polygon".
        coordinates (List[List[List[Float]]]): Outer ring + optional hole rings,
            each a list of [longitude, latitude] pairs.
    """

    coordinates = graphene.List(graphene.List(graphene.List(graphene.Float)))


class MultiPolygonFieldType(_CoordinatesTypeField):
    """GraphQL ObjectType for a MongoEngine MultiPolygonField (GeoJSON MultiPolygon).

    Fields:
        type (String): Always "MultiPolygon".
        coordinates (List[List[List[List[Float]]]]): A list of Polygon coordinate
            arrays, each following the PolygonFieldType convention.
    """

    coordinates = graphene.List(
        graphene.List(
            graphene.List(
                graphene.List(graphene.Float),
            )
        )
    )


class AwareDateTimeScalar(graphene.Scalar):
    """
    The `AwareDateTime` scalar type represents a DateTime value
    with extended timezone information as specified by RFC 9557 (IXDTF).

    Serialises to the Internet Extended Date/Time Format (IXDTF):
        "2024-05-16T12:00:00+09:00[Asia/Tokyo]"
         ↑ local wall-clock time    ↑ IANA timezone annotation
    """

    class Meta:
        name = "AwareDateTime"

    # Regex to match the RFC 3339 base and the IXDTF bracketed suffix
    REGEX = re.compile(r"([^\[]+)\[([^\]]+)\]")  # noqa: F821

    @staticmethod
    def serialize(dt) -> str:
        """Serialise a stored AwareDateTimeField value to an IXDTF string."""

        # 1. Reject strict date objects
        if type(dt) is datetime.date:
            raise GraphQLError(f"AwareDateTime cannot represent a date-only value: {repr(dt)}")

        # 2. Reject if it's not a datetime or completely lacks tzinfo
        if not isinstance(dt, datetime.datetime) or dt.tzinfo is None:
            raise GraphQLError(f"AwareDateTime requires a timezone-aware datetime: {repr(dt)}")

        # 3. Check for the region key
        tz_key = getattr(dt.tzinfo, "key", None)

        if tz_key is None:
            # Fallback scenario: No .key found (e.g., standard datetime.timezone.utc or a fixed offset)
            # Convert the datetime to true UTC so .isoformat() outputs "+00:00"
            dt = dt.astimezone(datetime.UTC)
            tz_key = "UTC"

        # 4. Construct the RFC 9557 format directly
        return f"{dt.isoformat()}[{tz_key}]"

    @classmethod
    def parse_literal(cls, node, _variables=None) -> datetime.datetime:
        """Parse a GraphQL string literal to a timezone-aware datetime."""
        if not isinstance(node, StringValueNode):
            raise GraphQLError(
                f"AwareDateTime cannot represent non-string value: {print_ast(node)}"
            )
        return cls.parse_value(node.value)

    @staticmethod
    def parse_value(value) -> datetime.datetime:
        """Parse an IXDTF string/datetime to a timezone-aware datetime."""
        if isinstance(value, datetime.datetime):
            return value
        if not isinstance(value, str):
            raise GraphQLError(f"AwareDateTime cannot represent non-string value: {repr(value)}")

        match = AwareDateTimeScalar.REGEX.match(value)

        if match:
            try:
                rfc3339_part, zone = match.groups()
                tz = ZoneInfo(zone)
                return datetime.datetime.fromisoformat(rfc3339_part).astimezone(tz)
            except ZoneInfoNotFoundError:
                raise GraphQLError(
                    f"Unknown timezone identifier in AwareDateTime value: {repr(value)}"
                )
            except ValueError:
                raise GraphQLError(f"AwareDateTime cannot represent value: {repr(value)}")

        raise GraphQLError(f"AwareDateTime cannot represent value: {repr(value)}")
