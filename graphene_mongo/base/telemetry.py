"""Optional OpenTelemetry tracing for graphene-mongo.

Gracefully degrades to a no-op when "opentelemetry-api` is not installed —
no import errors, no performance overhead beyond a single boolean check.

Span hierarchy produced per connection field resolution:

    graphql <field_name>          ← graphene-mongo (this module)
      └─ mongodb.aggregate        ← opentelemetry-instrumentation-pymongo (automatic)

Install the optional dependency to activate:

    pip install graphene-mongo[telemetry]
"""

from contextlib import contextmanager, nullcontext

try:
    from opentelemetry import trace
    from opentelemetry.trace import SpanKind, StatusCode

    _OTEL_AVAILABLE = True
except ImportError:
    _OTEL_AVAILABLE = False

_tracer = None


def _get_tracer():
    global _tracer
    if _tracer is None:
        _tracer = trace.get_tracer("graphene_mongo")
    return _tracer


def _set_graphql_attributes(span, info, args):
    """Populate standard GraphQL semantic attributes on *span*."""
    span.set_attribute("graphql.field.name", info.field_name)
    span.set_attribute("graphql.field.parent_type", info.parent_type.name)

    if info.operation:
        op_type = getattr(info.operation, "operation", None)
        if op_type is not None:
            span.set_attribute("graphql.operation.type", op_type.value)
        op_name = getattr(info.operation, "name", None)
        if op_name is not None:
            span.set_attribute("graphql.operation.name", op_name.value)

    for key in ("first", "last"):
        val = args.get(key)
        if val is not None:
            span.set_attribute(f"graphql.pagination.{key}", int(val))


@contextmanager
def field_span(info, args):
    """Context manager that wraps a connection field resolution in an OTEL span.

    Creates a child span named ``graphql <field_name>`` under whatever span is
    currently active (e.g., an HTTP server span).  All MongoDB commands issued
    inside the block become grandchildren via opentelemetry-instrumentation-pymongo.

    Marks the span as "ERROR" and records the exception if one propagates out.
    No-op when opentelemetry-api is not installed.

    Args:
        info: GraphQL resolve info object.
        args (dict): The raw GraphQL field arguments (first, last, before, after, …).

    Yields:
        opentelemetry.trace.Span | None
    """
    if not _OTEL_AVAILABLE:
        yield None
        return

    with _get_tracer().start_as_current_span(
        f"graphql {info.field_name}",
        kind=SpanKind.INTERNAL,
        record_exception=False,
        set_status_on_exception=False,
    ) as span:
        _set_graphql_attributes(span, info, args)
        try:
            yield span
        except Exception as exc:
            span.set_status(StatusCode.ERROR, str(exc))
            span.record_exception(exc)
            raise


@contextmanager
def node_span(info, type_name, node_id):
    """Context manager that wraps a ``get_node`` lookup in an OTEL span.

    Creates a child span named ``graphql node <TypeName>`` so Node.Field()
    lookups are traceable separately from connection field resolutions.

    Args:
        info: GraphQL resolve info object.
        type_name (str): The GraphQL type name (e.g. ``"ReporterNode"``).
        node_id (str): The Relay global ID being looked up.

    Yields:
        opentelemetry.trace.Span | None
    """
    if not _OTEL_AVAILABLE:
        yield None
        return

    with _get_tracer().start_as_current_span(
        f"graphql node {type_name}",
        kind=SpanKind.INTERNAL,
        record_exception=False,
        set_status_on_exception=False,
    ) as span:
        span.set_attribute("graphql.field.parent_type", type_name)
        span.set_attribute("graphql.node.id", str(node_id))

        if info.operation:
            op_type = getattr(info.operation, "operation", None)
            if op_type is not None:
                span.set_attribute("graphql.operation.type", op_type.value)
            op_name = getattr(info.operation, "name", None)
            if op_name is not None:
                span.set_attribute("graphql.operation.name", op_name.value)

        try:
            yield span
        except Exception as exc:
            span.set_status(StatusCode.ERROR, str(exc))
            span.record_exception(exc)
            raise