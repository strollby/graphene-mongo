# FastAPI + MongoEngine Example

GraphQL API for a library — `Author` and `Book` documents — built with
FastAPI, graphene-mongo async types, and Relay cursor pagination.

## Getting started

```bash
git clone https://github.com/graphql-python/graphene-mongo.git
cd graphene-mongo/examples/fastapi_mongoengine
uv sync
```

## Run

```bash
uv run uvicorn app:app --reload
```

Open the playground at [http://localhost:8000/graphql](http://localhost:8000/graphql).

## Sample queries

```graphql
# List books with their authors
query {
  books {
    edges {
      node {
        title
        genre
        publishedYear
        author { name nationality }
      }
    }
  }
}

# Filter by genre, paginate
query {
  books(genre: "Fiction", first: 5) {
    pageInfo { hasNextPage endCursor }
    edges {
      node { title publishedYear }
    }
  }
}

# Create a book
mutation {
  createBook(title: "Dune", publishedYear: 1965, genre: "Science Fiction") {
    book { id title }
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
               opentelemetry-instrumentation-fastapi \
               opentelemetry-instrumentation-pymongo \
               opentelemetry-exporter-otlp
```

```bash
OTEL_SERVICE_NAME=library-api \
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317 \
uv run uvicorn app:app --reload
```

### What you get

```
POST /graphql                          ← FastAPI HTTP span
  └─ graphql books                     ← graphene-mongo field_span
       └─ mongodb.aggregate            ← pymongo auto-instrumentation
  └─ graphql node AuthorType           ← graphene-mongo node_span
       └─ mongodb.aggregate
```

Each span carries:

| Attribute | Example value |
|---|---|
| `graphql.field.name` | `books` |
| `graphql.field.parent_type` | `Query` |
| `graphql.operation.type` | `query` |
| `graphql.operation.name` | `ListBooks` |
| `graphql.pagination.first` | `5` |

Errors set `StatusCode.ERROR` and attach the full stacktrace as an `exception` event.