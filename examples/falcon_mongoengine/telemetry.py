"""Optional OpenTelemetry setup for the Falcon example.

Install the extras to activate:

    pip install graphene-mongo[telemetry] \
                opentelemetry-instrumentation-falcon \
                opentelemetry-instrumentation-pymongo \
                opentelemetry-exporter-otlp

Then call setup_telemetry() inside MongoLifespan.process_startup().
Point OTEL_EXPORTER_OTLP_ENDPOINT at your collector (default: localhost:4317).
"""

import os


def setup_telemetry():
    """Instrument Falcon + pymongo and export spans via OTLP.

    Silently does nothing when opentelemetry packages are not installed.
    """
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
    provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint))
    )
    trace.set_tracer_provider(provider)

    PymongoInstrumentor().instrument()
    FalconInstrumentor().instrument()