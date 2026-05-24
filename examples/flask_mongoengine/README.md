# Flask + MongoEngine Example

GraphQL API for an HR domain — `Department`, `Employee`, `Role`, and `Task` documents —
built with Flask, graphene-mongo sync types, and Relay cursor pagination.

## Getting started

```bash
git clone https://github.com/graphql-python/graphene-mongo.git
cd graphene-mongo/examples/flask_mongoengine
uv sync
```

## Run

```bash
uv run python app.py
```

Open the playground at [http://localhost:5000/graphql](http://localhost:5000/graphql).

## Sample queries

```graphql
# List all employees with their department and roles
query {
    allEmployees {
        edges {
            node {
                id
                name
                department { id name }
                roles {
                    edges { node { id name } }
                }
                tasks {
                    edges { node { name deadline } }
                }
            }
        }
    }
}

# Filter employees by department name
query {
    allEmployees(department: "Engineering") {
        edges {
            node { name }
        }
    }
}
```

## Run tests

```bash
uv run pytest -v
```

## OpenTelemetry tracing

`telemetry.py` is already included. Install the extras and point the app at
your collector:

```bash
uv pip install "graphene-mongo[telemetry]" \
               opentelemetry-instrumentation-flask \
               opentelemetry-instrumentation-pymongo \
               opentelemetry-exporter-otlp
```

```bash
OTEL_SERVICE_NAME=hr-api \
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317 \
uv run python app.py
```

### What you get

```
POST /graphql                              ← Flask HTTP span
  └─ graphql allEmployees                  ← graphene-mongo field_span
       └─ mongodb.aggregate               ← pymongo auto-instrumentation
```

Each span carries:

| Attribute                   | Example value   |
|-----------------------------|-----------------|
| `graphql.field.name`        | `allEmployees`  |
| `graphql.field.parent_type` | `Query`         |
| `graphql.operation.type`    | `query`         |
| `graphql.operation.name`    | `ListEmployees` |
| `graphql.pagination.first`  | `10`            |

Errors set `StatusCode.ERROR` and attach the full stacktrace as an `exception` event.