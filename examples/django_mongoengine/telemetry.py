"""Optional OpenTelemetry setup for the Django example.

Install the extras to activate:

    pip install graphene-mongo[telemetry] \
                opentelemetry-instrumentation-django \
                opentelemetry-instrumentation-pymongo \
                opentelemetry-exporter-otlp

Then call setup_telemetry() inside BikeConfig.ready() in apps.py.
Point OTEL_EXPORTER_OTLP_ENDPOINT at your collector (default: localhost:4317).
"""

import os


def setup_telemetry():
    """Instrument Django + pymongo and export spans via OTLP.

    Silently does nothing when opentelemetry packages are not installed.
    """
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
    service_name = os.getenv("OTEL_SERVICE_NAME", "graphene-mongo-django")

    provider = TracerProvider()
    provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint))
    )
    trace.set_tracer_provider(provider)

    PymongoInstrumentor().instrument()
    DjangoInstrumentor().instrument()