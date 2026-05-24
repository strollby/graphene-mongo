"""Tests for graphene_mongo/base/telemetry.py."""

from unittest.mock import MagicMock

import pytest
from opentelemetry.trace import StatusCode


# ── Helpers ───────────────────────────────────────────────────────────────────


def make_info(field_name="articles", parent_type_name="Query", op_type="query", op_name="TestOp"):
    info = MagicMock()
    info.field_name = field_name
    info.parent_type.name = parent_type_name
    info.operation.operation.value = op_type
    info.operation.name.value = op_name
    return info


def make_tracer_and_span():
    span = MagicMock()
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=span)
    cm.__exit__ = MagicMock(return_value=False)
    tracer = MagicMock()
    tracer.start_as_current_span.return_value = cm
    return tracer, span


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_tracer(monkeypatch):
    """Replace _get_tracer with a mock so no real OTEL backend is needed."""
    import graphene_mongo.base.telemetry as telem

    tracer, span = make_tracer_and_span()
    monkeypatch.setattr(telem, "_get_tracer", lambda: tracer)
    return tracer, span


# ── No-op path (OTEL disabled) ────────────────────────────────────────────────


class TestFieldSpanNoOtel:
    def test_yields_none(self, monkeypatch):
        import graphene_mongo.base.telemetry as telem
        from graphene_mongo.base.telemetry import field_span

        monkeypatch.setattr(telem, "_OTEL_AVAILABLE", False)
        with field_span(make_info(), {}) as span:
            assert span is None

    def test_no_exception_on_clean_exit(self, monkeypatch):
        import graphene_mongo.base.telemetry as telem
        from graphene_mongo.base.telemetry import field_span

        monkeypatch.setattr(telem, "_OTEL_AVAILABLE", False)
        with field_span(make_info(), {"first": 10}):
            pass

    def test_propagates_exception(self, monkeypatch):
        import graphene_mongo.base.telemetry as telem
        from graphene_mongo.base.telemetry import field_span

        monkeypatch.setattr(telem, "_OTEL_AVAILABLE", False)
        with pytest.raises(ValueError, match="boom"):
            with field_span(make_info(), {}):
                raise ValueError("boom")


class TestNodeSpanNoOtel:
    def test_yields_none(self, monkeypatch):
        import graphene_mongo.base.telemetry as telem
        from graphene_mongo.base.telemetry import node_span

        monkeypatch.setattr(telem, "_OTEL_AVAILABLE", False)
        with node_span(make_info(), "ArticleType", "abc") as span:
            assert span is None

    def test_no_exception_on_clean_exit(self, monkeypatch):
        import graphene_mongo.base.telemetry as telem
        from graphene_mongo.base.telemetry import node_span

        monkeypatch.setattr(telem, "_OTEL_AVAILABLE", False)
        with node_span(make_info(), "ArticleType", "abc"):
            pass

    def test_propagates_exception(self, monkeypatch):
        import graphene_mongo.base.telemetry as telem
        from graphene_mongo.base.telemetry import node_span

        monkeypatch.setattr(telem, "_OTEL_AVAILABLE", False)
        with pytest.raises(RuntimeError, match="db error"):
            with node_span(make_info(), "ArticleType", "abc"):
                raise RuntimeError("db error")


# ── Active path — field_span ──────────────────────────────────────────────────


class TestFieldSpanWithOtel:
    def test_span_name_includes_field_name(self, mock_tracer):
        tracer, _ = mock_tracer
        from graphene_mongo.base.telemetry import field_span

        with field_span(make_info(field_name="articles"), {}):
            pass

        assert tracer.start_as_current_span.call_args[0][0] == "graphql articles"

    def test_yields_span(self, mock_tracer):
        _, span = mock_tracer
        from graphene_mongo.base.telemetry import field_span

        with field_span(make_info(), {}) as s:
            assert s is span

    def test_field_name_attribute(self, mock_tracer):
        _, span = mock_tracer
        from graphene_mongo.base.telemetry import field_span

        with field_span(make_info(field_name="reporters"), {}):
            pass

        span.set_attribute.assert_any_call("graphql.field.name", "reporters")

    def test_parent_type_attribute(self, mock_tracer):
        _, span = mock_tracer
        from graphene_mongo.base.telemetry import field_span

        with field_span(make_info(parent_type_name="Query"), {}):
            pass

        span.set_attribute.assert_any_call("graphql.field.parent_type", "Query")

    def test_operation_type_attribute(self, mock_tracer):
        _, span = mock_tracer
        from graphene_mongo.base.telemetry import field_span

        with field_span(make_info(op_type="mutation"), {}):
            pass

        span.set_attribute.assert_any_call("graphql.operation.type", "mutation")

    def test_operation_name_attribute(self, mock_tracer):
        _, span = mock_tracer
        from graphene_mongo.base.telemetry import field_span

        with field_span(make_info(op_name="MyQuery"), {}):
            pass

        span.set_attribute.assert_any_call("graphql.operation.name", "MyQuery")

    def test_pagination_first_attribute(self, mock_tracer):
        _, span = mock_tracer
        from graphene_mongo.base.telemetry import field_span

        with field_span(make_info(), {"first": 10}):
            pass

        span.set_attribute.assert_any_call("graphql.pagination.first", 10)

    def test_pagination_last_attribute(self, mock_tracer):
        _, span = mock_tracer
        from graphene_mongo.base.telemetry import field_span

        with field_span(make_info(), {"last": 5}):
            pass

        span.set_attribute.assert_any_call("graphql.pagination.last", 5)

    def test_no_pagination_attributes_when_absent(self, mock_tracer):
        _, span = mock_tracer
        from graphene_mongo.base.telemetry import field_span

        with field_span(make_info(), {}):
            pass

        calls_str = str(span.set_attribute.call_args_list)
        assert "pagination" not in calls_str

    def test_exception_recorded_on_span(self, mock_tracer):
        _, span = mock_tracer
        from graphene_mongo.base.telemetry import field_span

        exc = ValueError("boom")
        with pytest.raises(ValueError):
            with field_span(make_info(), {}):
                raise exc

        span.record_exception.assert_called_once_with(exc)

    def test_exception_sets_error_status(self, mock_tracer):
        _, span = mock_tracer
        from graphene_mongo.base.telemetry import field_span

        with pytest.raises(ValueError):
            with field_span(make_info(), {}):
                raise ValueError("boom")

        span.set_status.assert_called_once()
        assert span.set_status.call_args[0][0] == StatusCode.ERROR

    def test_exception_propagates(self, mock_tracer):
        from graphene_mongo.base.telemetry import field_span

        with pytest.raises(RuntimeError, match="propagated"):
            with field_span(make_info(), {}):
                raise RuntimeError("propagated")

    def test_no_error_status_on_clean_exit(self, mock_tracer):
        _, span = mock_tracer
        from graphene_mongo.base.telemetry import field_span

        with field_span(make_info(), {}):
            pass

        span.set_status.assert_not_called()
        span.record_exception.assert_not_called()


# ── Active path — node_span ───────────────────────────────────────────────────


class TestNodeSpanWithOtel:
    def test_span_name_includes_type_name(self, mock_tracer):
        tracer, _ = mock_tracer
        from graphene_mongo.base.telemetry import node_span

        with node_span(make_info(), "ArticleType", "abc"):
            pass

        assert tracer.start_as_current_span.call_args[0][0] == "graphql node ArticleType"

    def test_yields_span(self, mock_tracer):
        _, span = mock_tracer
        from graphene_mongo.base.telemetry import node_span

        with node_span(make_info(), "ArticleType", "abc") as s:
            assert s is span

    def test_parent_type_attribute(self, mock_tracer):
        _, span = mock_tracer
        from graphene_mongo.base.telemetry import node_span

        with node_span(make_info(), "ReporterType", "xyz"):
            pass

        span.set_attribute.assert_any_call("graphql.field.parent_type", "ReporterType")

    def test_node_id_attribute(self, mock_tracer):
        _, span = mock_tracer
        from graphene_mongo.base.telemetry import node_span

        with node_span(make_info(), "ArticleType", "abc123"):
            pass

        span.set_attribute.assert_any_call("graphql.node.id", "abc123")

    def test_node_id_is_stringified(self, mock_tracer):
        _, span = mock_tracer
        from graphene_mongo.base.telemetry import node_span

        with node_span(make_info(), "ArticleType", 42):
            pass

        span.set_attribute.assert_any_call("graphql.node.id", "42")

    def test_operation_type_attribute(self, mock_tracer):
        _, span = mock_tracer
        from graphene_mongo.base.telemetry import node_span

        with node_span(make_info(op_type="query"), "ArticleType", "x"):
            pass

        span.set_attribute.assert_any_call("graphql.operation.type", "query")

    def test_operation_name_attribute(self, mock_tracer):
        _, span = mock_tracer
        from graphene_mongo.base.telemetry import node_span

        with node_span(make_info(op_name="FetchNode"), "ArticleType", "x"):
            pass

        span.set_attribute.assert_any_call("graphql.operation.name", "FetchNode")

    def test_exception_recorded_on_span(self, mock_tracer):
        _, span = mock_tracer
        from graphene_mongo.base.telemetry import node_span

        exc = ValueError("not found")
        with pytest.raises(ValueError):
            with node_span(make_info(), "ArticleType", "abc"):
                raise exc

        span.record_exception.assert_called_once_with(exc)

    def test_exception_sets_error_status(self, mock_tracer):
        _, span = mock_tracer
        from graphene_mongo.base.telemetry import node_span

        with pytest.raises(ValueError):
            with node_span(make_info(), "ArticleType", "abc"):
                raise ValueError("not found")

        span.set_status.assert_called_once()
        assert span.set_status.call_args[0][0] == StatusCode.ERROR

    def test_exception_propagates(self, mock_tracer):
        from graphene_mongo.base.telemetry import node_span

        with pytest.raises(RuntimeError, match="not found"):
            with node_span(make_info(), "ArticleType", "abc"):
                raise RuntimeError("not found")

    def test_no_error_status_on_clean_exit(self, mock_tracer):
        _, span = mock_tracer
        from graphene_mongo.base.telemetry import node_span

        with node_span(make_info(), "ArticleType", "abc"):
            pass

        span.set_status.assert_not_called()
        span.record_exception.assert_not_called()