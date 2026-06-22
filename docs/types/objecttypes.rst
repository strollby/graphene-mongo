Types and Meta Options
======================

``MongoengineObjectType`` and ``AsyncMongoengineObjectType`` are the core classes
that convert MongoEngine documents into Graphene types.

Defining a type
---------------

Sync:

.. code:: python

    from graphene_mongo import MongoengineObjectType

    class ArticleType(MongoengineObjectType):
        class Meta:
            model = ArticleModel       # required
            interfaces = (Node,)       # enables Relay pagination

Async:

.. code:: python

    from graphene_mongo import AsyncMongoengineObjectType

    class ArticleType(AsyncMongoengineObjectType):
        class Meta:
            model = ArticleModel
            interfaces = (Node,)

All MongoEngine fields on the model are converted automatically.
See :doc:`/types/fields` for the full mapping.

Meta options reference
----------------------

All options are declared inside the nested ``Meta`` class.

``model`` — *Document class* — **required**
    The MongoEngine document to expose.

``interfaces`` — *tuple*
    e.g. ``(Node,)`` — enables Relay cursor pagination and global ``Node.Field()`` lookup.

``only_fields`` — *tuple[str]*
    Whitelist of field names to expose. All other fields are hidden.

``exclude_fields`` — *tuple[str]*
    Field names to hide from the schema. Inverse of ``only_fields``.

``required_fields`` — *tuple[str]*
    Fields always fetched from the DB regardless of what the client selected.
    Useful for fields needed by resolvers that aren't directly queried.

``non_required_fields`` — *tuple[str]*
    Force these graphene fields to be non-required, even if the MongoEngine
    field has ``required=True``.

``filter_fields`` — *dict*
    Lookup-style filter arguments auto-generated on the connection field.
    Example: ``{"name": ["exact", "icontains"], "age": ["gte", "lte"]}``.
    See :doc:`/types/filtering` for supported operators.

``non_filter_fields`` — *tuple[str]*
    Fields excluded from auto-generated filter arguments.

``order_by`` — *str*
    Default MongoEngine ordering expression applied to all queries.
    Example: ``"-created_at"`` (descending), ``"name"`` (ascending).

``registry`` — *Registry*
    Explicit type registry. Useful for isolating types between test modules
    or building multiple schemas in one process.

``connection_field_class`` — *type*
    Override the connection field class used for this type's connections.

Examples
--------

Whitelist fields:

.. code:: python

    class UserType(MongoengineObjectType):
        class Meta:
            model = UserModel
            only_fields = ("id", "email", "name")

Exclude sensitive fields:

.. code:: python

    class UserType(MongoengineObjectType):
        class Meta:
            model = UserModel
            exclude_fields = ("password_hash", "internal_notes")

Enable filtering:

.. code:: python

    class ArticleType(MongoengineObjectType):
        class Meta:
            model = ArticleModel
            interfaces = (Node,)
            filter_fields = {
                "title": ["exact", "icontains", "istartswith"],
                "published": ["exact"],
                "view_count": ["gte", "lte"],
            }

Default ordering:

.. code:: python

    class ArticleType(MongoengineObjectType):
        class Meta:
            model = ArticleModel
            interfaces = (Node,)
            order_by = "-published_at"   # newest first