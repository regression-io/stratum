"""
Built-in OTLP emitter.

POSTs HTTP/JSON to any OTLP endpoint. No opentelemetry-sdk dependency required.
Configure via: stratum.configure(tracer=stratum.exporters.otel(endpoint="..."))
"""

from __future__ import annotations

import json
import secrets
import time
import threading
from typing import Any
from urllib.request import urlopen, Request
from urllib.error import URLError


def otel(
    endpoint: str = "http://localhost:4318/v1/traces",
    service_name: str = "stratum",
    timeout_seconds: float = 5.0,
) -> Any:
    """
    Factory that returns a tracer callable compatible with stratum.configure(tracer=...).

    The returned callable accepts a dict of span attributes and POSTs them
    as an OTLP HTTP/JSON trace to the configured endpoint.

    Usage:
        stratum.configure(tracer=stratum.exporters.otel(endpoint="http://localhost:4318/v1/traces"))
    """

    def _emit(span_attrs: dict[str, Any]) -> None:
        """
        Fire-and-forget OTLP span emission.

        Runs in a daemon thread so it never blocks the calling coroutine.
        Errors are silently swallowed — tracer failures must not affect execution.
        """

        def _post() -> None:
            try:
                now_ns = int(time.time_ns())
                body = _build_otlp_body(span_attrs, service_name, now_ns)
                payload = json.dumps(body).encode("utf-8")
                req = Request(
                    endpoint,
                    data=payload,
                    headers={
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                    },
                    method="POST",
                )
                with urlopen(req, timeout=timeout_seconds) as resp:
                    resp.read()  # drain
            except (URLError, OSError, Exception):
                pass  # silently swallow all tracer errors

        t = threading.Thread(target=_post, daemon=True)
        t.start()

    return _emit


def _build_otlp_body(
    span_attrs: dict[str, Any],
    service_name: str,
    now_ns: int,
) -> dict:
    """
    Build a minimal OTLP HTTP/JSON trace body with a single span.

    Conforms to OpenTelemetry Semantic Conventions for AI:
    https://opentelemetry.io/docs/specs/semconv/gen-ai/
    """
    # Convert attribute dict to OTLP KeyValue list
    kv_attrs = _attrs_to_kv(span_attrs)

    # Service resource attributes
    resource_attrs = _attrs_to_kv({"service.name": service_name})

    # Derive span name from stratum.function if present
    span_name = span_attrs.get("stratum.function", "stratum.infer")

    # Derive start time from duration_ms so spans have correct duration
    duration_ms = span_attrs.get("stratum.duration_ms")
    if duration_ms is not None:
        start_time_unix_nano = now_ns - int(duration_ms * 1_000_000)
    else:
        start_time_unix_nano = now_ns
    end_time_unix_nano = now_ns

    # Use flow_id as traceId so all @infer spans within a @flow share the same
    # trace and appear together in OTLP backends. flow_id is a UUID4 — strip
    # hyphens to get the 32-hex-char format OTLP requires. Fall back to a
    # fresh random ID for @infer calls made outside a @flow.
    flow_id: str | None = span_attrs.get("stratum.flow_id")
    trace_id = flow_id.replace("-", "") if flow_id else secrets.token_hex(16)

    body = {
        "resourceSpans": [
            {
                "resource": {
                    "attributes": resource_attrs,
                },
                "scopeSpans": [
                    {
                        "scope": {
                            "name": "stratum",
                            "version": "0.1.0",
                        },
                        "spans": [
                            {
                                "traceId": trace_id,
                                "spanId": secrets.token_hex(8),     # 64-bit random, unique per span
                                "name": span_name,
                                "kind": 3,  # CLIENT
                                "startTimeUnixNano": str(start_time_unix_nano),
                                "endTimeUnixNano": str(end_time_unix_nano),
                                "attributes": kv_attrs,
                                "status": {"code": 1},  # OK
                            }
                        ],
                    }
                ],
            }
        ]
    }
    return body


def _attrs_to_kv(attrs: dict[str, Any]) -> list[dict]:
    """Convert a flat dict to OTLP KeyValue list."""
    result = []
    for key, value in attrs.items():
        if value is None:
            continue
        if isinstance(value, bool):
            kv = {"key": key, "value": {"boolValue": value}}
        elif isinstance(value, int):
            kv = {"key": key, "value": {"intValue": str(value)}}
        elif isinstance(value, float):
            kv = {"key": key, "value": {"doubleValue": value}}
        else:
            kv = {"key": key, "value": {"stringValue": str(value)}}
        result.append(kv)
    return result
