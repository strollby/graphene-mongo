Falcon
======

Full source: ``examples/falcon_mongoengine``

Bookmarks domain: ``Category`` and ``Bookmark`` documents.

.. code:: bash

    cd examples/falcon_mongoengine
    pip install -e ".[dev]"
    uvicorn app:app --reload --port 9000

.. code:: bash

    curl -X POST http://localhost:9000/graphql \
      -H "Content-Type: application/json" \
      -d '{"query": "{ categories { edges { node { name color } } } }"}'

Running tests:

.. code:: bash

    cd examples/falcon_mongoengine
    pytest -v

OpenTelemetry
-------------

Install extras:

.. code:: bash

    pip install "graphene-mongo[telemetry]" \
                opentelemetry-instrumentation-falcon \
                opentelemetry-instrumentation-pymongo \
                opentelemetry-exporter-otlp

``telemetry.py``

.. code:: python

    import os

    def setup_telemetry():
        try:
            from opentelemetry import trace
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
            from opentelemetry.instrumentation.falcon import FalconInstrumentor
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
        FalconInstrumentor().instrument()

Call it from the ASGI lifespan handler:

.. code:: python

    # app.py
    import falcon.asgi
    from telemetry import setup_telemetry

    async def process_startup(scope, event):
        setup_telemetry()

Run:

.. code:: bash

    OTEL_SERVICE_NAME=bookmarks-api \
    OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317 \
    uvicorn app:app --reload --port 9000

Span output:

.. code:: text

    POST /graphql                       ← Falcon HTTP span
      └─ graphql bookmarks              ← graphene-mongo field span
           └─ mongodb.aggregate         ← pymongo auto-instrumentation