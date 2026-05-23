[![Build Status](https://travis-ci.org/graphql-python/graphene-mongo.svg?branch=master)](https://travis-ci.org/graphql-python/graphene-mongo) [![Coverage Status](https://coveralls.io/repos/github/graphql-python/graphene-mongo/badge.svg?branch=master)](https://coveralls.io/github/graphql-python/graphene-mongo?branch=master) [![Documentation Status](https://readthedocs.org/projects/graphene-mongo/badge/?version=latest)](http://graphene-mongo.readthedocs.io/en/latest/?badge=latest) [![PyPI version](https://badge.fury.io/py/graphene-mongo.svg)](https://badge.fury.io/py/graphene-mongo) [![PyPI pyversions](https://img.shields.io/pypi/pyversions/graphene-mongo.svg)](https://pypi.python.org/pypi/graphene-mongo/) [![Downloads](https://pepy.tech/badge/graphene-mongo)](https://pepy.tech/project/graphene-mongo)

[![Lint](https://github.com/graphql-python/graphene-mongo/actions/workflows/lint.yml/badge.svg?branch=master)](https://github.com/graphql-python/graphene-mongo/actions/workflows/lint.yml) [![Test Package](https://github.com/graphql-python/graphene-mongo/actions/workflows/ci.yml/badge.svg)](https://github.com/graphql-python/graphene-mongo/actions/workflows/ci.yml)

# Graphene-Mongo

A [Mongoengine](https://mongoengine-odm.readthedocs.io/) integration for [Graphene](http://graphene-python.org/).

## Installation

For installing graphene-mongo, just run this command in your shell

```
pip install graphene-mongo
```

## Examples

Here is a simple Mongoengine model as `models.py`:

```python
from mongoengine import Document
from mongoengine.fields import StringField


class User(Document):
    meta = {'collection': 'user'}
    first_name = StringField(required=True)
    last_name = StringField(required=True)
```

To create a GraphQL schema and sync executor; for it you simply have to write the following:

```python
import graphene

from graphene_mongo import MongoengineObjectType

from .models import User as UserModel


class User(MongoengineObjectType):
    class Meta:
        model = UserModel


class Query(graphene.ObjectType):
    users = graphene.List(User)

    def resolve_users(self, info):
        return list(UserModel.objects.all())


schema = graphene.Schema(query=Query)
```

Then you can simply query the schema:

```python
query = '''
    query {
        users {
            firstName,
            lastName
        }
    }
'''
result = await schema.execute(query)
```

To create a GraphQL schema and async executor; for it you simply have to write the following:

```python
import graphene

from graphene_mongo import AsyncMongoengineObjectType

from .models import User as UserModel


class User(AsyncMongoengineObjectType):
    class Meta:
        model = UserModel


class Query(graphene.ObjectType):
    users = graphene.List(User)

    async def resolve_users(self, info):
        return await UserModel.aobjects.to_list()


schema = graphene.Schema(query=Query)
```

Then you can simply query the schema:

```python
query = '''
    query {
        users {
            firstName,
            lastName
        }
    }
'''
result = await schema.execute_async(query)
```

## Meta Options

All options are declared inside the nested `Meta` class of an ObjectType.

| Option                   | Type             | Description                                                             |
|--------------------------|------------------|-------------------------------------------------------------------------|
| `model`                  | `Document` class | **Required.** The MongoEngine document to expose.                       |
| `interfaces`             | `tuple`          | e.g. `(Node,)` — enables Relay cursor pagination.                       |
| `only_fields`            | `tuple[str]`     | Whitelist of field names to expose.                                     |
| `exclude_fields`         | `tuple[str]`     | Field names to hide from the schema.                                    |
| `required_fields`        | `tuple[str]`     | Fields always fetched from the DB regardless of query selection.        |
| `non_required_fields`    | `tuple[str]`     | Force these graphene fields to be non-required.                         |
| `filter_fields`          | `dict`           | Lookup-style filter arguments, e.g. `{"name": ["exact", "icontains"]}`. |
| `non_filter_fields`      | `tuple[str]`     | Fields excluded from auto-generated filter arguments.                   |
| `order_by`               | `str`            | Default MongoEngine ordering expression, e.g. `"-created_at"`.          |
| `registry`               | `Registry`       | Explicit type registry (useful for isolating types in tests).           |
| `connection_field_class` | `type`           | Override the connection field class for this type.                      |

## Field Type Mapping

MongoEngine fields are converted to GraphQL types automatically:

| MongoEngine                             | GraphQL                                                            |
|-----------------------------------------|--------------------------------------------------------------------|
| `StringField`, `EmailField`, `URLField` | `String`                                                           |
| `IntField`, `SequenceField`             | `Int`                                                              |
| `FloatField`                            | `Float`                                                            |
| `BooleanField`                          | `Boolean`                                                          |
| `DateTimeField`                         | `DateTime`                                                         |
| `DateField`                             | `Date`                                                             |
| `DecimalField`, `Decimal128Field`       | `Decimal`                                                          |
| `UUIDField`, `ObjectIdField`            | `ID`                                                               |
| `DictField`, `MapField`                 | `JSONString`                                                       |
| `FileField`                             | `FileFieldType` (`contentType`, `md5`, `length`, `data` as base64) |
| `PointField`                            | `PointFieldType` (`type`, `coordinates`)                           |
| `PolygonField`                          | `PolygonFieldType`                                                 |
| `MultiPolygonField`                     | `MultiPolygonFieldType`                                            |
| `ReferenceField`                        | Resolved graphene type (lazy, via `Dynamic`)                       |
| `EmbeddedDocumentField`                 | Resolved graphene type (lazy, via `Dynamic`)                       |
| `ListField(ReferenceField(...))`        | `List` or `ConnectionField` if the target is a Relay `Node`        |
| `GenericReferenceField`                 | `Union` of registered `choices`                                    |
| `EnumField`                             | `graphene.Enum` (auto-registered)                                  |

To learn more check out the following [examples](examples/):

* [Flask MongoEngine example](examples/flask_mongoengine)
* [Django MongoEngine example](examples/django_mongoengine)
* [Falcon MongoEngine example](examples/falcon_mongoengine)
* [FastAPI MongoEngine example](examples/fastapi_mongoengine)

## Contributing

After cloning this repo, ensure dependencies are installed by running:

```sh
uv sync
```

After developing, the full test suite can be evaluated by running:

```sh
uv run make test
```
