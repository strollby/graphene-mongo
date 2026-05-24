Field Type Mapping
==================

MongoEngine fields are converted to GraphQL types automatically when you define a
``MongoengineObjectType`` or ``AsyncMongoengineObjectType``.

Scalar Fields
-------------

``StringField``, ``EmailField``, ``URLField``
    ``String``

``IntField``, ``SequenceField``
    ``Int``

``FloatField``
    ``Float``

``BooleanField``
    ``Boolean``

``DateTimeField``
    ``DateTime``

``DateField``
    ``Date``

``DecimalField``, ``Decimal128Field``
    ``Decimal``

``UUIDField``, ``ObjectIdField``
    ``ID``

``DictField``, ``MapField``
    ``JSONString``

Special Fields
--------------

``FileField``
    ``FileFieldType`` — sub-fields: ``contentType``, ``md5``, ``length``, ``data`` (base64).

``PointField``
    ``PointFieldType`` — sub-fields: ``type``, ``coordinates``.

``PolygonField``
    ``PolygonFieldType``

``MultiPolygonField``
    ``MultiPolygonFieldType``

``EnumField``
    ``graphene.Enum`` (auto-registered from the Python enum class).

Reference Fields
----------------

``ReferenceField`` resolves to the target graphene type. When queried through a
connection field, the referenced document is pre-fetched in a single aggregation.
See :doc:`/prefetching/index` for how this works.

.. code:: python

    class Author(mongoengine.Document):
        name = mongoengine.StringField()

    class Book(mongoengine.Document):
        title = mongoengine.StringField()
        author = mongoengine.ReferenceField(Author)

    # author resolved in one aggregate — no N+1
    # { books { edges { node { title author { name } } } } }

``GenericReferenceField`` becomes a GraphQL union type automatically:

.. code:: python

    class Article(mongoengine.Document): ...
    class Video(mongoengine.Document): ...

    class Feed(mongoengine.Document):
        item = mongoengine.GenericReferenceField(choices=[Article, Video])

Embedded Documents
------------------

``EmbeddedDocumentField`` becomes a nested GraphQL object.
``ListField(EmbeddedDocumentField(...))`` becomes a Relay connection.

.. code:: python

    class Address(mongoengine.EmbeddedDocument):
        street = mongoengine.StringField()
        city = mongoengine.StringField()

    class Task(mongoengine.EmbeddedDocument):
        name = mongoengine.StringField()

    class Person(mongoengine.Document):
        address = mongoengine.EmbeddedDocumentField(Address)
        tasks = mongoengine.ListField(mongoengine.EmbeddedDocumentField(Task))

List of References
------------------

``ListField(ReferenceField(...))`` becomes a ``List`` or a Relay ``ConnectionField``
when the target has a ``Node`` interface:

.. code:: python

    class Employee(mongoengine.Document):
        name = mongoengine.StringField()
        roles = mongoengine.ListField(mongoengine.ReferenceField(Role))
        tags = mongoengine.ListField(mongoengine.StringField())

Self-Referential Fields
-----------------------

A document can reference itself — graphene-mongo handles the circular dependency:

.. code:: python

    class Employee(mongoengine.Document):
        name = mongoengine.StringField()
        leader = mongoengine.ReferenceField("self")
        reports = mongoengine.ListField(mongoengine.ReferenceField("self"))

Inheritance
-----------

MongoEngine document inheritance is supported. Child types are registered
separately and resolved as GraphQL union types through ``GenericReferenceField``:

.. code:: python

    class Animal(mongoengine.Document):
        name = mongoengine.StringField()
        meta = {"allow_inheritance": True}

    class Dog(Animal):
        breed = mongoengine.StringField()