import re

from graphene.relay.connection import (
    ConnectionOptions,
    Enum,
    Field,
    Int,
    Interface,
    List,
    NonNull,
    ObjectType,
    PageInfo,
    Scalar,
    Union,
    get_edge_class,
)


class PageConnection(ObjectType):
    class Meta:
        abstract = True

    @classmethod
    def __init_subclass_with_meta__(
        cls, node=None, name=None, strict_types=False, _meta=None, **options
    ):
        if not _meta:
            _meta = ConnectionOptions(cls)
        assert node, f"You have to provide a node in {cls.__name__}.Meta"
        assert isinstance(node, NonNull) or issubclass(
            node, (Scalar, Enum, ObjectType, Interface, Union, NonNull)
        ), f'Received incompatible node "{node}" for Connection {cls.__name__}.'

        base_name = re.sub("Connection$", "", name or cls.__name__) or node._meta.name
        if not name:
            name = f"{base_name}Connection"

        options["name"] = name

        _meta.node = node

        if not _meta.fields:
            _meta.fields = {}

        if "page_info" not in _meta.fields:
            _meta.fields["page_info"] = Field(
                PageInfo,
                name="pageInfo",
                required=True,
                description="Pagination data for this connection.",
            )

        if "page_count" not in _meta.fields:
            _meta.fields["page_count"] = Field(
                Int,
                required=True,
                description="Page count data for this connection. This is a heavy computation, always call once only",
            )

        if "edges" not in _meta.fields:
            edge_class = get_edge_class(cls, node, base_name, strict_types)  # type: ignore
            cls.Edge = edge_class
            _meta.fields["edges"] = Field(
                NonNull(List(NonNull(edge_class) if strict_types else edge_class)),
                description="Contains the nodes in this connection.",
            )

        return super(PageConnection, cls).__init_subclass_with_meta__(_meta=_meta, **options)
