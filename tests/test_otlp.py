"""Tests for the built-in OTLP exporter."""

from __future__ import annotations

import json
import os
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from stratum.exporters.otlp import _attrs_to_kv, _build_otlp_body, otel


# ---------------------------------------------------------------------------
# _attrs_to_kv
# ---------------------------------------------------------------------------

class TestAttrsToKv:
    def test_string_value(self):
        result = _attrs_to_kv({"key": "value"})
        assert result == [{"key": "key", "value": {"stringValue": "value"}}]

    def test_int_value_encoded_as_string(self):
        result = _attrs_to_kv({"count": 5})
        assert result == [{"key": "count", "value": {"intValue": "5"}}]

    def test_float_value(self):
        result = _attrs_to_kv({"cost": 0.001})
        assert result == [{"key": "cost", "value": {"doubleValue": 0.001}}]

    def test_bool_value(self):
        result = _attrs_to_kv({"flag": True})
        assert result == [{"key": "flag", "value": {"boolValue": True}}]

    def test_none_value_excluded(self):
        result = _attrs_to_kv({"present": "yes", "absent": None})
        assert len(result) == 1
        assert result[0]["key"] == "present"

    def test_empty_dict_returns_empty_list(self):
        assert _attrs_to_kv({}) == []

    def test_multiple_values_all_present(self):
        result = _attrs_to_kv({"a": 1, "b": "two", "c": 3.14})
        keys = {kv["key"] for kv in result}
        assert keys == {"a", "b", "c"}


# ---------------------------------------------------------------------------
# _build_otlp_body
# ---------------------------------------------------------------------------

class TestBuildOtlpBody:
    def test_has_resource_spans(self):
        body = _build_otlp_body({"stratum.function": "fn"}, "stratum", 0)
        assert "resourceSpans" in body
        assert len(body["resourceSpans"]) == 1

    def test_service_name_in_resource(self):
        body = _build_otlp_body({}, "my-service", 0)
        resource_attrs = body["resourceSpans"][0]["resource"]["attributes"]
        svc = next(a for a in resource_attrs if a["key"] == "service.name")
        assert svc["value"]["stringValue"] == "my-service"

    def test_span_name_from_function_attr(self):
        body = _build_otlp_body({"stratum.function": "classify"}, "s", 0)
        span = body["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
        assert span["name"] == "classify"

    def test_span_name_defaults_to_stratum_infer(self):
        body = _build_otlp_body({}, "s", 0)
        span = body["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
        assert span["name"] == "stratum.infer"

    def test_span_kind_is_client(self):
        body = _build_otlp_body({}, "s", 0)
        span = body["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
        assert span["kind"] == 3  # CLIENT

    def test_span_status_ok(self):
        body = _build_otlp_body({}, "s", 0)
        span = body["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
        assert span["status"]["code"] == 1  # OK

    def test_custom_attrs_included_in_span(self):
        body = _build_otlp_body({"stratum.attempts": 2, "stratum.cost_usd": 0.005}, "s", 0)
        span = body["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
        attr_keys = {a["key"] for a in span["attributes"]}
        assert "stratum.attempts" in attr_keys
        assert "stratum.cost_usd" in attr_keys

    def test_start_time_encoded(self):
        ts = 1_700_000_000_000_000_000
        body = _build_otlp_body({}, "s", ts)
        span = body["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
        assert span["startTimeUnixNano"] == str(ts)

    def test_scope_name_is_stratum(self):
        body = _build_otlp_body({}, "s", 0)
        scope = body["resourceSpans"][0]["scopeSpans"][0]["scope"]
        assert scope["name"] == "stratum"

    def test_body_is_json_serializable(self):
        body = _build_otlp_body(
            {"stratum.function": "fn", "stratum.cost_usd": 0.001, "stratum.attempts": 1},
            "stratum",
            int(time.time_ns()),
        )
        serialized = json.dumps(body)
        assert len(serialized) > 0
        # Round-trip
        assert json.loads(serialized)["resourceSpans"][0]["scopeSpans"][0]["spans"][0]["name"] == "fn"


# ---------------------------------------------------------------------------
# otel factory
# ---------------------------------------------------------------------------

class TestOtelFactory:
    def test_returns_callable(self):
        emitter = otel(endpoint="http://localhost:4318/v1/traces")
        assert callable(emitter)

    def test_different_endpoints_return_independent_callables(self):
        e1 = otel(endpoint="http://host1:4318/v1/traces")
        e2 = otel(endpoint="http://host2:4318/v1/traces")
        assert e1 is not e2

    def test_emitter_does_not_block(self):
        """Emitter fires in a daemon thread and returns immediately."""
        emitter = otel(endpoint="http://localhost:19999/v1/traces")  # non-existent
        start = time.monotonic()
        emitter({"stratum.function": "test_fn", "stratum.attempts": 1})
        elapsed = time.monotonic() - start
        # Should return in well under 1s even though the endpoint doesn't exist
        assert elapsed < 1.0

    def test_emitter_swallows_connection_error(self):
        """URLError from a bad endpoint must not propagate to the caller."""
        emitter = otel(endpoint="http://localhost:19999/nope")
        # Should not raise
        emitter({"stratum.function": "test", "stratum.cost_usd": 0.0})
        time.sleep(0.1)  # let the daemon thread attempt and fail silently

    def test_emitter_accepts_full_span_attrs(self):
        """Emitter should handle all expected stratum span attribute types."""
        emitter = otel(endpoint="http://localhost:19999/v1/traces")
        attrs = {
            "stratum.function": "classify",
            "stratum.model": "claude-sonnet-4-6",
            "stratum.attempts": 2,
            "stratum.cost_usd": 0.001,
            "stratum.duration_ms": 342,
            "stratum.cache_hit": False,
            "stratum.flow_id": "abc123",
            "stratum.contract_hash": "def456",
        }
        # Should not raise regardless of network
        emitter(attrs)
        time.sleep(0.05)
