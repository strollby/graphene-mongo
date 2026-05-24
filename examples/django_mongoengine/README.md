# Django + MongoEngine Example

GraphQL API for a bike shop — `Bike` and `Shop` documents — built with
Django, graphene-django, graphene-mongo sync types, and Relay cursor pagination.

## Getting started

```bash
git clone https://github.com/graphql-python/graphene-mongo.git
cd graphene-mongo/examples/django_mongoengine
uv sync
```

## Run

```bash
uv run python manage.py migrate
uv run python manage.py runserver
```

Open the playground at [http://localhost:8000/graphql](http://localhost:8000/graphql).

## Sample queries

```graphql
# List all bikes
query {
  bikes {
    edges {
      node {
        id
        name
        year
        brand
        speed
      }
    }
  }
}

# Create a bike
mutation {
  createBike(name: "Trail Blazer", year: 2024, brand: "Trek", speed: 21) {
    bike { id name year brand }
  }
}

# Update a bike
mutation {
  updateBike(id: "<relay-id>", speed: 24) {
    bike { id name speed }
  }
}

# Delete a bike
mutation {
  deleteBike(id: "<relay-id>") {
    ok
  }
}
```

## Run tests

```bash
uv run pytest -v
```

## OpenTelemetry tracing

`telemetry.py` is already included and called from `BikeConfig.ready()` in `bike/apps.py`.
Install the extras and point the app at your collector:

```bash
uv pip install "graphene-mongo[telemetry]" \
               opentelemetry-instrumentation-django \
               opentelemetry-instrumentation-pymongo \
               opentelemetry-exporter-otlp
```

```bash
OTEL_SERVICE_NAME=bike-shop-api \
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317 \
uv run python manage.py runserver
```

### What you get

```
GET /graphql                           ← Django HTTP span
  └─ graphql bikes                     ← graphene-mongo field_span
       └─ mongodb.aggregate            ← pymongo auto-instrumentation
  └─ graphql node BikeType             ← graphene-mongo node_span
       └─ mongodb.aggregate
```

Each span carries:

| Attribute | Example value |
|---|---|
| `graphql.field.name` | `bikes` |
| `graphql.field.parent_type` | `Query` |
| `graphql.operation.type` | `query` |
| `graphql.operation.name` | `ListBikes` |
| `graphql.node.id` | `QmlrZVR5cGU6NjY...` |

Errors set `StatusCode.ERROR` and attach the full stacktrace as an `exception` event.