Django
======

Full source: ``examples/django_mongoengine``

Bike shop domain: ``Bike`` and ``Shop`` documents.

.. code:: bash

    cd examples/django_mongoengine
    pip install -e ".[dev]"
    python manage.py migrate
    python manage.py runserver

Open the playground at `http://localhost:8000/graphql <http://localhost:8000/graphql>`_.

Sample queries:

.. code:: graphql

    query {
        bikes {
            edges {
                node { id name year brand speed }
            }
        }
    }

    mutation {
        createBike(name: "Trail Blazer", year: 2024, brand: "Trek", speed: 21) {
            bike { id name year brand }
        }
    }

Running tests:

.. code:: bash

    cd examples/django_mongoengine
    pytest -v

OpenTelemetry
-------------

Install extras:

.. code:: bash

    pip install "graphene-mongo[telemetry]" \
                opentelemetry-instrumentation-django \
                opentelemetry-instrumentation-pymongo \
                opentelemetry-exporter-otlp

``telemetry.py``

.. code:: python

    import os

    def setup_telemetry():
        try:
            from opentelemetry import trace
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
            from opentelemetry.instrumentation.django import DjangoInstrumentor
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
        DjangoInstrumentor().instrument()

Call it from ``AppConfig.ready()``:

.. code:: python

    # bike/apps.py
    from django.apps import AppConfig

    class BikeConfig(AppConfig):
        name = "bike"

        def ready(self):
            from telemetry import setup_telemetry
            setup_telemetry()

Run:

.. code:: bash

    OTEL_SERVICE_NAME=bike-shop-api \
    OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317 \
    python manage.py runserver

Span output:

.. code:: text

    GET /graphql                        ← Django HTTP span
      └─ graphql bikes                  ← graphene-mongo field span
           └─ mongodb.aggregate         ← pymongo auto-instrumentation
      └─ graphql node BikeType          ← graphene-mongo node span
           └─ mongodb.aggregate