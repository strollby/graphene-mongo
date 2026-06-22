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

## How It Works

### Automatic Query-Driven Pre-fetching

The central design principle is: **fetch exactly what the GraphQL client asked for, in as few MongoDB round-trips as
possible.**

When a connection field resolves, graphene-mongo inspects the incoming GraphQL selection set before the query runs. It
walks every field the client requested and collects the MongoEngine reference paths that need to be resolved — including
nested references (e.g. `article → editor → company`). These paths are passed directly to MongoEngine's
`select_related`, which compiles them into a single MongoDB aggregation pipeline using `$lookup` stages.

```graphql
query {
    articles {
        edges {
            node {
                headline
                editor {
                    firstName
                    company { name }
                }
            }
        }
    }
}
```

The library detects that `editor` and `editor.company` are referenced fields, then issues:

```python
Article.aobjects.select_related("editor", "editor__company")
```

This becomes **one** aggregation with two `$lookup` stages — no N+1, no lazy deref, no hidden thread pools.

### What `select_related` covers

| Field type                  | Example               | Behaviour                                                                  |
|-----------------------------|-----------------------|----------------------------------------------------------------------------|
| `ReferenceField`            | `article.editor`      | Pre-fetched; nested refs also recursed (e.g. `editor__company`)            |
| `ListField(ReferenceField)` | `parent.before_child` | List hydrated; nested refs inside each element also pre-fetched via `$map` |
| `EmbeddedDocumentField`     | `professor.metadata`  | Always co-located in the document — no extra query                         |
| `GenericReferenceField`     | `item.content`        | Union resolved; choices pre-fetched                                        |

### Sync vs Async

Both execution modes share the same pre-fetching logic. The difference is in the QuerySet manager used:

- **Sync** (`MongoengineObjectType`) — uses `model.objects`, resolvers are plain functions.
- **Async** (`AsyncMongoengineObjectType`) — uses `model.aobjects`, resolvers are `async def`. The pipeline_builder
  compiles everything into a single `aggregate()` call.

### Custom `get_queryset`

You can supply a `get_queryset` callback on a connection field to apply custom filters. The library applies
`select_related` on top of whatever queryset or filter dict you return, so pre-fetching still works:

```python
def get_queryset(model, info, **args):
    return model.objects(published=True)  # filters only — select_related added automatically


articles = MongoengineConnectionField(ArticleNode, get_queryset=get_queryset)
```

If you return a `QuerySet` or `AsyncQuerySet`, `select_related` is applied to it automatically — your filters are
preserved and the referenced fields the client asked for are pre-fetched on top, all in one aggregation. If you return
a dict, it is used as filter kwargs and the same pre-fetching applies.

### `Node.Field()` and `get_node`

The default `get_node` on both `MongoengineObjectType` and `AsyncMongoengineObjectType` already applies
`select_related` automatically — it inspects the GraphQL selection set and pre-fetches only the referenced
fields the client asked for, in a single aggregation.

If you override `get_node` for custom filtering or access control, you must replicate this yourself or
referenced fields will be unhydrated:

```python
from graphene_mongo import get_query_fields, get_select_related_paths


class ReporterNode(AsyncMongoengineObjectType):
    class Meta:
        model = Reporter
        interfaces = (Node,)

    @classmethod
    async def get_node(cls, info, id):
        # ⚠ Always derive and apply select_related when overriding get_node
        queried = get_query_fields(info)
        paths = get_select_related_paths(cls._meta.model, queried)
        qs = cls._meta.model.aobjects.filter(pk=id)
        if paths:
            qs = qs.select_related(*paths)
        return await qs.first()
```

Omitting `select_related` here will cause referenced fields to be unhydrated — they will resolve to `None`
or raise an error depending on whether async lazy dereferencing is supported.

### Custom resolvers on ObjectTypes

If you write a resolver directly on a `Query` class for a `graphene.Field` (single document), you are fully
in control — return the document directly. Hard-coding `select_related` paths works but over-fetches when the
client doesn't request those fields and silently breaks when new reference fields are added to the model.
Use `get_query_fields` + `get_select_related_paths` instead so pre-fetching adapts automatically:

```python
from graphene_mongo import get_query_fields, get_select_related_paths


# ✗ hard-coded — over-fetches, breaks silently when model changes
async def resolve_reporter(self, info):
    return await Reporter.aobjects.select_related("articles", "company").first()


# ✓ query-driven — fetches only what the client asked for
async def resolve_reporter(self, info):
    queried = get_query_fields(info)
    paths = get_select_related_paths(Reporter, queried)
    return await Reporter.aobjects.select_related(*paths).first()
```

### Pre-fetching in `graphene.List` resolvers

Connection fields apply `select_related` automatically. If you use `graphene.List` or write a single-document
resolver outside the connection pipeline, you are responsible for calling `select_related` yourself.
Two utilities are exported to help:

```python
from graphene_mongo import get_query_fields, get_select_related_paths

# Derive the paths the client actually queried
queried = get_query_fields(info)  # {"editor": {"firstName": {}}, ...}
paths = get_select_related_paths(Reporter, queried)  # ["editor", "editor__company"]

# Apply only what the client asked for
qs = Reporter.aobjects.filter(active=True).select_related(*paths)
```

`get_query_fields` returns the nested selection-set dict from the GraphQL AST.
`get_select_related_paths` walks that dict against the MongoEngine model and returns `__`-separated paths
suitable for `QuerySet.select_related`.

## OpenTelemetry Tracing

graphene-mongo has built-in OpenTelemetry support. Install the optional extra to activate it:

```sh
pip install graphene-mongo[telemetry]
```

When `opentelemetry-api` is installed, the library emits spans automatically — no code changes required
in your resolvers or schema. When it is not installed, the library runs with zero overhead (a single
boolean check per resolution).

### Span hierarchy

```
POST /graphql                      ← framework HTTP span (FastAPI / Flask / Falcon / Django)
  └─ graphql articles              ← graphene-mongo  (connection field resolution)
       └─ mongodb.aggregate        ← opentelemetry-instrumentation-pymongo (automatic)
  └─ graphql node ReporterType     ← graphene-mongo  (Node.Field / get_node lookup)
       └─ mongodb.aggregate
```

### Attributes set on each span

| Attribute                   | Value                                           |
|-----------------------------|-------------------------------------------------|
| `graphql.field.name`        | The field name being resolved                   |
| `graphql.field.parent_type` | The parent GraphQL type name                    |
| `graphql.operation.type`    | `query`, `mutation`, or `subscription`          |
| `graphql.operation.name`    | The named operation (if provided by the client) |
| `graphql.pagination.first`  | Value of `first` argument (connection fields)   |
| `graphql.pagination.last`   | Value of `last` argument (connection fields)    |
| `graphql.node.id`           | The Relay global ID (node lookups only)         |

Spans are marked `ERROR` and the exception is recorded (with full stacktrace) if an unhandled exception
propagates out of the resolver. MongoDB-level spans are produced automatically by
`opentelemetry-instrumentation-pymongo` and appear as children.

### Wiring up a backend

Each framework example in this repo includes a ready-to-use `telemetry.py` with
`setup_telemetry()` that creates a `TracerProvider`, attaches a `BatchSpanProcessor` with an
OTLP exporter, instruments pymongo, and instruments the framework. Call it once at app startup
and set `OTEL_EXPORTER_OTLP_ENDPOINT` to point at your collector (Jaeger, Datadog Agent,
Grafana Tempo, etc.).

Full wiring instructions and sample span output for each framework:

- [FastAPI example](examples/fastapi_mongoengine/README.md)
- [Flask example](examples/flask_mongoengine/README.md)
- [Falcon example](examples/falcon_mongoengine/README.md)
- [Django example](examples/django_mongoengine/README.md)

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
