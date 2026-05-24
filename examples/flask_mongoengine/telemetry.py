"""Optional OpenTelemetry setup for the Flask example.

Install the extras to activate:

    pip install graphene-mongo[telemetry] \
                opentelemetry-instrumentation-flask \
                opentelemetry-instrumentation-pymongo \
                opentelemetry-exporter-otlp

Then call setup_telemetry(app) before app.run().
Point OTEL_EXPORTER_OTLP_ENDPOINT at your collector (default: localhost:4317).
"""

import os


def setup_telemetry(app):
    """Instrument Flask + pymongo and export spans via OTLP.

    Silently does nothing when opentelemetry packages are not installed.
    """
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
    provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint))
    )
    trace.set_tracer_provider(provider)

    PymongoInstrumentor().instrument()
    FlaskInstrumentor().instrument_app(app)