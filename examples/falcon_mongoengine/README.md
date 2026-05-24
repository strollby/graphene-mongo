# Falcon + MongoEngine Example

GraphQL API for a bookmarks manager — `Category` and `Bookmark` documents —
built with Falcon ASGI, graphene-mongo sync types, and Relay cursor pagination.

## Getting started

```bash
git clone https://github.com/graphql-python/graphene-mongo.git
cd graphene-mongo/examples/falcon_mongoengine
uv sync
```

## Run

```bash
uv run uvicorn app:app --reload --port 9000
```

Send queries via HTTP:

```bash
curl -X POST http://localhost:9000/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "{ categories { edges { node { name color } } } }"}'
```

## Sample queries

```graphql
# List categories
query {
  categories {
    edges {
      node { name color }
    }
  }
}

# List bookmarks with pagination and their category
query {
  bookmarks(first: 10) {
    pageInfo { hasNextPage endCursor }
    edges {
      node {
        name
        url
        tags
        category { name color }
      }
    }
  }
}

# Filter by category name
query {
  categories(name: "Travel") {
    edges { node { name color } }
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
               opentelemetry-instrumentation-falcon \
               opentelemetry-instrumentation-pymongo \
               opentelemetry-exporter-otlp
```

```bash
OTEL_SERVICE_NAME=bookmarks-api \
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317 \
uv run uvicorn app:app --reload --port 9000
```

### What you get

```
POST /graphql                          ← Falcon HTTP span
  └─ graphql bookmarks                 ← graphene-mongo field_span
       └─ mongodb.aggregate            ← pymongo auto-instrumentation
```

Each span carries:

| Attribute | Example value |
|---|---|
| `graphql.field.name` | `bookmarks` |
| `graphql.field.parent_type` | `Query` |
| `graphql.operation.type` | `query` |
| `graphql.operation.name` | `ListBookmarks` |
| `graphql.pagination.first` | `10` |

Errors set `StatusCode.ERROR` and attach the full stacktrace as an `exception` event.