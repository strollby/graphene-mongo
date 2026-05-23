import base64

import graphene
from graphene_federation import shareable


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
            field: The graphene field instance; must carry ``instance`` and
                ``key`` attributes pointing to the parent document and field name.
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
            str | None: UTF-8 base64 string, or ``None`` if the file is empty.
        """
        v = getattr(self.instance, self.key)
        data = v.read()
        if data is not None:
            return base64.b64encode(data).decode("utf-8")
        return None


@shareable  # Support Graphene Federation v2
class _CoordinatesTypeField(graphene.ObjectType):
    """Internal base ObjectType for GeoJSON geometry types.

    Provides the ``type`` string field (e.g. ``"Point"``) shared by all
    GeoJSON geometry shapes. Subclasses add the appropriate ``coordinates``
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
        type (String): Always ``"Point"``.
        coordinates (List[Float]): ``[longitude, latitude]``.
    """

    coordinates = graphene.List(graphene.Float)


class PointFieldInputType(graphene.InputObjectType):
    """GraphQL InputObjectType for filtering or mutating a MongoEngine PointField.

    Used as an argument type when querying by geographic point.

    Fields:
        type (String): GeoJSON geometry type; defaults to ``"Point"``.
        coordinates (List[Float]): Required ``[longitude, latitude]`` pair.
    """

    type = graphene.String(default_value="Point")
    coordinates = graphene.List(graphene.Float, required=True)


class PolygonFieldType(_CoordinatesTypeField):
    """GraphQL ObjectType for a MongoEngine PolygonField (GeoJSON Polygon).

    Fields:
        type (String): Always ``"Polygon"``.
        coordinates (List[List[List[Float]]]): Outer ring + optional hole rings,
            each a list of ``[longitude, latitude]`` pairs.
    """

    coordinates = graphene.List(graphene.List(graphene.List(graphene.Float)))


class MultiPolygonFieldType(_CoordinatesTypeField):
    """GraphQL ObjectType for a MongoEngine MultiPolygonField (GeoJSON MultiPolygon).

    Fields:
        type (String): Always ``"MultiPolygon"``.
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
