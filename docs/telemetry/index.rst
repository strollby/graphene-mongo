OpenTelemetry Tracing
======================

graphene-mongo has built-in OpenTelemetry support. Install the optional extra
to activate it:

.. code:: bash

    pip install "graphene-mongo[telemetry]"

When ``opentelemetry-api`` is installed, the library emits spans automatically —
no code changes required in your resolvers or schema. When it is not installed,
the library runs with zero overhead (a single boolean check per resolution).

.. rubric:: Span hierarchy

.. code:: text

    POST /graphql                      ← framework HTTP span
      └─ graphql articles              ← graphene-mongo (connection field)
           └─ mongodb.aggregate        ← opentelemetry-instrumentation-pymongo
      └─ graphql node ReporterType     ← graphene-mongo (Node.Field lookup)
           └─ mongodb.aggregate

.. rubric:: Span attributes

``graphql.field.name``
    The field name being resolved (e.g. ``articles``, ``node``).

``graphql.field.parent_type``
    The parent GraphQL type name (e.g. ``Query``).

``graphql.operation.type``
    ``query``, ``mutation``, or ``subscription``.

``graphql.operation.name``
    The named operation if provided by the client (e.g. ``ListArticles``).

``graphql.pagination.first``
    Value of the ``first`` argument on connection fields.

``graphql.pagination.last``
    Value of the ``last`` argument on connection fields.

``graphql.node.id``
    The Relay global ID — set on node lookups (``Node.Field()``) only.

Spans are marked ``ERROR`` and the exception is recorded (with full stacktrace)
if an unhandled exception propagates out of the resolver.

.. rubric:: Running with a collector

Point the app at any OTLP-compatible collector (Jaeger, Grafana Tempo, Datadog Agent):

.. code:: bash

    OTEL_SERVICE_NAME=my-api \
    OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317 \
    python app.py

For Datadog, enable OTLP in ``datadog.yaml`` and use the Agent's gRPC intake:

.. code:: bash

    OTEL_SERVICE_NAME=my-api \
    OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317 \
    DD_OTLP_CONFIG_RECEIVER_PROTOCOLS_GRPC_ENDPOINT=0.0.0.0:4317 \
    python app.py

.. rubric:: Testing spans

Use ``InMemorySpanExporter`` from ``opentelemetry-sdk`` to capture spans in tests:

.. code:: python

    import pytest
    import graphene_mongo.base.telemetry as telem
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    @pytest.fixture
    def exporter(monkeypatch):
        mem_exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(mem_exporter))
        tracer = provider.get_tracer("graphene_mongo")
        monkeypatch.setattr(telem, "_get_tracer", lambda: tracer)
        yield mem_exporter

    def test_span_emitted(exporter, schema):
        schema.execute("{ articles { edges { node { title } } } }")
        spans = exporter.get_finished_spans()
        assert spans[0].name == "graphql articles"
        assert spans[0].attributes["graphql.field.name"] == "articles"