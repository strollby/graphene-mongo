Flask
=====

Full source: ``examples/flask_mongoengine``

HR domain: ``Department``, ``Employee``, ``Role``, and ``Task`` documents.

.. code:: bash

    cd examples/flask_mongoengine
    pip install -e ".[dev]"
    python app.py

Open the playground at `http://localhost:5000/graphql <http://localhost:5000/graphql>`_.

Sample queries:

.. code:: graphql

    query {
        allEmployees {
            edges {
                node {
                    id
                    name
                    department { id name }
                    roles { edges { node { id name } } }
                    tasks { edges { node { name deadline } } }
                }
            }
        }
    }

Running tests:

.. code:: bash

    cd examples/flask_mongoengine
    pytest -v

OpenTelemetry
-------------

Install extras:

.. code:: bash

    pip install "graphene-mongo[telemetry]" \
                opentelemetry-instrumentation-flask \
                opentelemetry-instrumentation-pymongo \
                opentelemetry-exporter-otlp

``telemetry.py``

.. code:: python

    import os

    def setup_telemetry(app):
        try:
            from opentelemetry import trace
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
            from opentelemetry.instrumentation.flask import FlaskInstrumentor
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
        FlaskInstrumentor().instrument_app(app)

Wire it in ``app.py``:

.. code:: python

    from flask import Flask
    from telemetry import setup_telemetry

    app = Flask(__name__)
    setup_telemetry(app)

Run:

.. code:: bash

    OTEL_SERVICE_NAME=hr-api \
    OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317 \
    python app.py

Span output:

.. code:: text

    POST /graphql                       ← Flask HTTP span
      └─ graphql allEmployees           ← graphene-mongo field span
           └─ mongodb.aggregate         ← pymongo auto-instrumentation