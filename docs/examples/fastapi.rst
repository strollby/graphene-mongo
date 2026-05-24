FastAPI
=======

Full source: ``examples/fastapi_mongoengine``

Library domain: ``Author`` and ``Book`` documents.

.. code:: bash

    cd examples/fastapi_mongoengine
    pip install -e ".[dev]"
    uvicorn app:app --reload

Open the playground at `http://localhost:8000/graphql <http://localhost:8000/graphql>`_.

Sample queries:

.. code:: graphql

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

    mutation {
        createBook(title: "Dune", publishedYear: 1965, genre: "Science Fiction") {
            book { id title }
        }
    }

Running tests:

.. code:: bash

    cd examples/fastapi_mongoengine
    pytest -v

OpenTelemetry
-------------

Install extras:

.. code:: bash

    pip install "graphene-mongo[telemetry]" \
                opentelemetry-instrumentation-fastapi \
                opentelemetry-instrumentation-pymongo \
                opentelemetry-exporter-otlp

``telemetry.py``

.. code:: python

    import os

    def setup_telemetry(app):
        try:
            from opentelemetry import trace
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
            from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
            from opentelemetry.instrumentation.pymongo import PymongoInstrumentor
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor
        except ImportError:
            return
        endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
        provider = TracerProvider()
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
        trace.set_tracer_provider(provider)
        PymongoInstrumentor().instrument()
        FastAPIInstrumentor.instrument_app(app)

Wire it in ``app.py``:

.. code:: python

    from fastapi import FastAPI
    from telemetry import setup_telemetry

    app = FastAPI()
    setup_telemetry(app)

Run:

.. code:: bash

    OTEL_SERVICE_NAME=library-api \
    OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317 \
    uvicorn app:app --reload

Span output:

.. code:: text

    POST /graphql                  ← FastAPI HTTP span
      └─ graphql books             ← graphene-mongo field span
           └─ mongodb.aggregate    ← pymongo auto-instrumentation
      └─ graphql node AuthorType   ← graphene-mongo node span
           └─ mongodb.aggregate