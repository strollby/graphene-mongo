"""Demonstrates what an OTEL exporter receives from graphene-mongo spans.

Uses InMemorySpanExporter (part of opentelemetry-sdk) to capture real spans
and assert on the data a production exporter (Jaeger, OTLP, etc.) would see.
"""

from unittest.mock import MagicMock

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import SpanKind, StatusCode


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def exporter(monkeypatch):
    """Wire a real TracerProvider + InMemorySpanExporter into graphene-mongo.

    Creates a local TracerProvider (not the global one — OTEL only allows
    setting the global provider once per process) and patches _get_tracer
    to return a tracer from it directly.
    """
    import graphene_mongo.base.telemetry as telem

    mem_exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(mem_exporter))

    tracer = provider.get_tracer("graphene_mongo")
    monkeypatch.setattr(telem, "_get_tracer", lambda: tracer)

    yield mem_exporter


def make_info(field_name="articles", parent_type_name="Query", op_type="query", op_name="GetArticles"):
    info = MagicMock()
    info.field_name = field_name
    info.parent_type.name = parent_type_name
    info.operation.operation.value = op_type
    info.operation.name.value = op_name
    return info


# ── field_span exporter output ────────────────────────────────────────────────


class TestFieldSpanExporter:
    def test_span_is_exported(self, exporter):
        from graphene_mongo.base.telemetry import field_span

        with field_span(make_info(field_name="articles"), {}):
            pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 1

    def test_span_name(self, exporter):
        from graphene_mongo.base.telemetry import field_span

        with field_span(make_info(field_name="articles"), {}):
            pass

        span = exporter.get_finished_spans()[0]
        assert span.name == "graphql articles"

    def test_span_kind_is_internal(self, exporter):
        from graphene_mongo.base.telemetry import field_span

        with field_span(make_info(), {}):
            pass

        span = exporter.get_finished_spans()[0]
        assert span.kind == SpanKind.INTERNAL

    def test_graphql_attributes(self, exporter):
        from graphene_mongo.base.telemetry import field_span

        with field_span(
                make_info(field_name="articles", parent_type_name="Query", op_type="query", op_name="GetArticles"), {}):
            pass

        attrs = exporter.get_finished_spans()[0].attributes
        assert attrs["graphql.field.name"] == "articles"
        assert attrs["graphql.field.parent_type"] == "Query"
        assert attrs["graphql.operation.type"] == "query"
        assert attrs["graphql.operation.name"] == "GetArticles"

    def test_pagination_attributes(self, exporter):
        from graphene_mongo.base.telemetry import field_span

        with field_span(make_info(), {"first": 10, "last": None}):
            pass

        attrs = exporter.get_finished_spans()[0].attributes
        assert attrs["graphql.pagination.first"] == 10
        assert "graphql.pagination.last" not in attrs

    def test_status_ok_on_clean_exit(self, exporter):
        from graphene_mongo.base.telemetry import field_span

        with field_span(make_info(), {}):
            pass

        span = exporter.get_finished_spans()[0]
        assert span.status.status_code == StatusCode.UNSET

    def test_status_error_on_exception(self, exporter):
        from graphene_mongo.base.telemetry import field_span

        with pytest.raises(RuntimeError):
            with field_span(make_info(), {}):
                raise RuntimeError("db connection lost")

        span = exporter.get_finished_spans()[0]
        assert span.status.status_code == StatusCode.ERROR
        assert "db connection lost" in span.status.description

    def test_exception_event_recorded(self, exporter):
        from graphene_mongo.base.telemetry import field_span

        with pytest.raises(ValueError):
            with field_span(make_info(), {}):
                raise ValueError("invalid filter")

        span = exporter.get_finished_spans()[0]
        # record_exception() adds an "exception" event to the span
        assert len(span.events) == 1
        event = span.events[0]
        assert event.name == "exception"
        assert "invalid filter" in event.attributes["exception.message"]
        assert event.attributes["exception.type"] == "ValueError"


# ── node_span exporter output ─────────────────────────────────────────────────


class TestNodeSpanExporter:
    def test_span_is_exported(self, exporter):
        from graphene_mongo.base.telemetry import node_span

        with node_span(make_info(), "ArticleType", "abc123"):
            pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 1

    def test_span_name(self, exporter):
        from graphene_mongo.base.telemetry import node_span

        with node_span(make_info(), "ArticleType", "abc123"):
            pass

        assert exporter.get_finished_spans()[0].name == "graphql node ArticleType"

    def test_span_kind_is_internal(self, exporter):
        from graphene_mongo.base.telemetry import node_span

        with node_span(make_info(), "ArticleType", "abc123"):
            pass

        assert exporter.get_finished_spans()[0].kind == SpanKind.INTERNAL

    def test_node_attributes(self, exporter):
        from graphene_mongo.base.telemetry import node_span

        with node_span(make_info(op_type="query", op_name="FetchNode"), "ArticleType", "abc123"):
            pass

        attrs = exporter.get_finished_spans()[0].attributes
        assert attrs["graphql.field.parent_type"] == "ArticleType"
        assert attrs["graphql.node.id"] == "abc123"
        assert attrs["graphql.operation.type"] == "query"
        assert attrs["graphql.operation.name"] == "FetchNode"

    def test_status_error_on_exception(self, exporter):
        from graphene_mongo.base.telemetry import node_span

        with pytest.raises(LookupError):
            with node_span(make_info(), "ArticleType", "abc123"):
                raise LookupError("document not found")

        span = exporter.get_finished_spans()[0]
        assert span.status.status_code == StatusCode.ERROR

    def test_exception_event_recorded(self, exporter):
        from graphene_mongo.base.telemetry import node_span

        with pytest.raises(LookupError):
            with node_span(make_info(), "ArticleType", "abc123"):
                raise LookupError("document not found")

        event = exporter.get_finished_spans()[0].events[0]
        assert event.name == "exception"
        assert event.attributes["exception.type"] == "LookupError"
        assert "document not found" in event.attributes["exception.message"]
