Supported Fields
================

All standard Mongoengine fields are automatically converted to the appropriate
Graphene scalar or type when you define a ``MongoengineObjectType`` or
``AsyncMongoengineObjectType``.

Scalar Fields
-------------

+-------------------------------+--------------------------+
| Mongoengine Field             | GraphQL / Graphene Type  |
+===============================+==========================+
| ``BooleanField``              | ``Boolean``              |
+-------------------------------+--------------------------+
| ``DateTimeField``             | ``DateTime``             |
+-------------------------------+--------------------------+
| ``DecimalField``              | ``Float``                |
+-------------------------------+--------------------------+
| ``DictField``                 | ``JSONString``           |
+-------------------------------+--------------------------+
| ``EmailField``                | ``String``               |
+-------------------------------+--------------------------+
| ``FloatField``                | ``Float``                |
+-------------------------------+--------------------------+
| ``IntField``                  | ``Int``                  |
+-------------------------------+--------------------------+
| ``ObjectIdField``             | ``ID``                   |
+-------------------------------+--------------------------+
| ``SequenceField``             | ``Int``                  |
+-------------------------------+--------------------------+
| ``StringField``               | ``String``               |
+-------------------------------+--------------------------+
| ``URLField``                  | ``String``               |
+-------------------------------+--------------------------+
| ``UUIDField``                 | ``String``               |
+-------------------------------+--------------------------+

Reference Fields
----------------

ReferenceField
~~~~~~~~~~~~~~

Resolves to the related document type. When queried through
``MongoengineConnectionField`` or ``AsyncMongoengineConnectionField``,
the referenced document is pre-fetched via ``select_related()`` —
no extra query per document.

.. code:: python

    class Author(mongoengine.Document):
        name = mongoengine.StringField()

    class Book(mongoengine.Document):
        title = mongoengine.StringField()
        author = mongoengine.ReferenceField(Author)

    # query: author resolved in one aggregate, not N+1
    { books { edges { node { title author { name } } } } }

GenericReferenceField
~~~~~~~~~~~~~~~~~~~~~

A field that can reference documents of different types. Rendered as a
GraphQL union type automatically from the ``choices`` list:

.. code:: python

    class Article(mongoengine.Document): ...
    class Video(mongoengine.Document): ...

    class Feed(mongoengine.Document):
        item = mongoengine.GenericReferenceField(choices=[Article, Video])

Embedded Documents
------------------

EmbeddedDocumentField
~~~~~~~~~~~~~~~~~~~~~

Nested sub-document, rendered as a nested GraphQL object:

.. code:: python

    class Address(mongoengine.EmbeddedDocument):
        street = mongoengine.StringField()
        city = mongoengine.StringField()

    class Person(mongoengine.Document):
        address = mongoengine.EmbeddedDocumentField(Address)

EmbeddedDocumentListField
~~~~~~~~~~~~~~~~~~~~~~~~~

List of embedded sub-documents, rendered as a Relay connection:

.. code:: python

    class Task(mongoengine.EmbeddedDocument):
        name = mongoengine.StringField()

    class Employee(mongoengine.Document):
        tasks = mongoengine.ListField(mongoengine.EmbeddedDocumentField(Task))

List Fields
-----------

ListField
~~~~~~~~~

Rendered as a GraphQL list. When the inner field is a ``ReferenceField``,
it becomes a list of the related type:

.. code:: python

    class Employee(mongoengine.Document):
        roles = mongoengine.ListField(mongoengine.ReferenceField(Role))
        tags = mongoengine.ListField(mongoengine.StringField())

MapField
~~~~~~~~

Rendered as ``JSONString``.

Geo Fields
----------

+-------------------------------+----------------------------------+
| Mongoengine Field             | Notes                            |
+===============================+==================================+
| ``PointField``                | ``[longitude, latitude]``        |
+-------------------------------+----------------------------------+
| ``PolygonField``              | GeoJSON polygon                  |
+-------------------------------+----------------------------------+
| ``MultiPolygonField``         | GeoJSON multi-polygon            |
+-------------------------------+----------------------------------+

File Fields
-----------

FileField
~~~~~~~~~

GridFS file field. Rendered as a ``FileFieldType`` with ``data``,
``contentType``, ``length``, and ``chunkSize`` sub-fields:

.. code:: graphql

    { editors { edges { node { avatar { contentType length } } } } }

Advanced
--------

Self-Referential Fields
~~~~~~~~~~~~~~~~~~~~~~~

A document can reference itself. graphene-mongo handles the circular
dependency automatically:

.. code:: python

    class Employee(mongoengine.Document):
        name = mongoengine.StringField()
        leader = mongoengine.ReferenceField("self")
        reports = mongoengine.ListField(mongoengine.ReferenceField("self"))

Inheritance
~~~~~~~~~~~

Mongoengine document inheritance is supported. Child types are registered
separately and resolved as GraphQL union types when queried through a
``GenericReferenceField``:

.. code:: python

    class Animal(mongoengine.Document):
        name = mongoengine.StringField()
        meta = {"allow_inheritance": True}

    class Dog(Animal):
        breed = mongoengine.StringField()

filter_fields
~~~~~~~~~~~~~

All connection fields support ``filter_fields`` for inline filtering:

.. code:: python

    class BookType(MongoengineObjectType):
        class Meta:
            model = Book
            interfaces = (Node,)
            filter_fields = {
                "title": ["exact", "icontains", "istartswith"],
                "published_year": ["exact", "gte", "lte"],
            }

Supported operators: ``exact``, ``iexact``, ``contains``, ``icontains``,
``startswith``, ``istartswith``, ``in``, ``nin``, ``lt``, ``lte``, ``gt``,
``gte``, ``ne``.