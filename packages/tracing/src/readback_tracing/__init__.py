"""OpenTelemetry spans for readback, exported to Parquet, with no message content captured.

Span names and attributes follow the GenAI semantic conventions as pinned in docs/observability.md
(read 2026-10-23, still in development status upstream): one invoke_agent span per turn, a chat span
per model call with the provider, the request and response model, the finish reasons and the token
counts, an execute_tool span per tool call, and the gate as its own span with its verdict. The MCP
SDK's own server spans join the same trace, because the agent puts traceparent and tracestate into
each request's metadata and the server reads them.

The question text and the answer text are never attributes; a test asserts it. The Parquet exporter
is the default and the only one; an OTLP exporter is added when OTEL_EXPORTER_OTLP_ENDPOINT is set.
"""

from __future__ import annotations

import json
import os
import threading
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from opentelemetry import propagate, trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter, SpanExportResult
from opentelemetry.trace import Span, SpanKind, Status, StatusCode

SERVICE = "readback"
# The attribute names in use, pinned. docs/observability.md lists them with the date they were read.
ATTR = {
    "operation": "gen_ai.operation.name",
    "provider": "gen_ai.provider.name",
    "request_model": "gen_ai.request.model",
    "response_model": "gen_ai.response.model",
    "finish_reasons": "gen_ai.response.finish_reasons",
    "input_tokens": "gen_ai.usage.input_tokens",
    "output_tokens": "gen_ai.usage.output_tokens",
    "tool_name": "gen_ai.tool.name",
    "tool_call_id": "gen_ai.tool.call.id",
    "agent_name": "gen_ai.agent.name",
    "conversation": "gen_ai.conversation.id",
}
# Attributes that would carry content. None of them is ever set; the test reads every span for them.
CONTENT_ATTRIBUTES = (
    "gen_ai.input.messages",
    "gen_ai.output.messages",
    "gen_ai.system_instructions",
    "gen_ai.prompt",
    "gen_ai.completion",
)


class ParquetSpanExporter(SpanExporter):
    """Keeps finished spans in memory; write() puts them in a Parquet file, one row per span."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._spans: list[ReadableSpan] = []

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        with self._lock:
            self._spans.extend(spans)
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        return None

    def clear(self) -> None:
        with self._lock:
            self._spans.clear()

    @property
    def spans(self) -> list[ReadableSpan]:
        with self._lock:
            return list(self._spans)

    def rows(self, trace_id: str | None = None) -> list[dict[str, Any]]:
        out = []
        for s in self.spans:
            ctx = s.get_span_context()
            if ctx is None:
                continue
            tid = format(ctx.trace_id, "032x")
            if trace_id and tid != trace_id:
                continue
            out.append(
                {
                    "trace_id": tid,
                    "span_id": format(ctx.span_id, "016x"),
                    "parent_id": format(s.parent.span_id, "016x") if s.parent else None,
                    "name": s.name,
                    "kind": s.kind.name.lower(),
                    "start_ns": int(s.start_time or 0),
                    "end_ns": int(s.end_time or 0),
                    "status": s.status.status_code.name.lower(),
                    "attributes": {str(k): _plain(v) for k, v in sorted((s.attributes or {}).items())},
                }
            )
        out.sort(key=lambda r: (r["trace_id"], r["start_ns"], r["span_id"]))
        return out

    def write(self, path: Path, trace_id: str | None = None) -> int:
        import pyarrow as pa
        import pyarrow.parquet as pq

        rows = self.rows(trace_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        keys = sorted({k for r in rows for k in r["attributes"]})
        attr_type = (
            pa.struct([(k, pa.string()) for k in keys]) if keys else pa.struct([("none", pa.string())])
        )
        table = pa.table(
            {
                "trace_id": [r["trace_id"] for r in rows],
                "span_id": [r["span_id"] for r in rows],
                "parent_id": [r["parent_id"] for r in rows],
                "name": [r["name"] for r in rows],
                "kind": [r["kind"] for r in rows],
                "start_ns": pa.array([r["start_ns"] for r in rows], pa.int64()),
                "end_ns": pa.array([r["end_ns"] for r in rows], pa.int64()),
                "status": [r["status"] for r in rows],
                "attributes": pa.array(
                    [
                        {
                            k: (None if r["attributes"].get(k) is None else str(r["attributes"][k]))
                            for k in keys
                        }
                        if keys
                        else {"none": None}
                        for r in rows
                    ],
                    attr_type,
                ),
            }
        )
        pq.write_table(table, path, compression="zstd")
        return len(rows)


def _plain(value: Any) -> Any:
    if isinstance(value, (tuple, list)):
        return json.dumps(list(value))
    return value


_EXPORTER: ParquetSpanExporter | None = None
_INSTALL_LOCK = threading.Lock()


def install() -> ParquetSpanExporter:
    """Install the tracer provider once per process and return its Parquet exporter."""
    global _EXPORTER
    with _INSTALL_LOCK:
        if _EXPORTER is not None:
            return _EXPORTER
        provider = TracerProvider(
            resource=Resource.create({"service.name": os.environ.get("OTEL_SERVICE_NAME", SERVICE)})
        )
        exporter = ParquetSpanExporter()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        if os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
            try:
                from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

                provider.add_span_processor(SimpleSpanProcessor(OTLPSpanExporter()))
            except ImportError:  # the OTLP exporter is an optional dependency
                pass
        trace.set_tracer_provider(provider)
        _EXPORTER = exporter
        return exporter


def tracer() -> trace.Tracer:
    install()
    return trace.get_tracer("readback")


def trace_id_of(span: Span) -> str:
    return format(span.get_span_context().trace_id, "032x")


def carrier() -> dict[str, str]:
    """traceparent and tracestate for the current span, for an MCP request's metadata."""
    out: dict[str, str] = {}
    propagate.inject(out)
    return out


@contextmanager
def agent_span(
    conversation: str, family: str | None = None, parent: dict[str, str] | None = None
) -> Iterator[Span]:
    """A turn's span. A turn resumed from a checkpoint passes the traceparent it stored, so the resumed
    work joins the trace it started in, and the result handles minted in that trace stay valid."""
    context = propagate.extract(parent) if parent else None
    with tracer().start_as_current_span(
        "invoke_agent readback",
        context=context,
        kind=SpanKind.INTERNAL,
        attributes={
            ATTR["operation"]: "invoke_agent",
            ATTR["agent_name"]: "readback",
            ATTR["conversation"]: conversation,
        },
    ) as span:
        if family:
            span.set_attribute("readback.family", family)
        yield span


@contextmanager
def chat_span(provider: str, model: str) -> Iterator[Span]:
    with tracer().start_as_current_span(
        f"chat {model}",
        kind=SpanKind.CLIENT,
        attributes={ATTR["operation"]: "chat", ATTR["provider"]: provider, ATTR["request_model"]: model},
    ) as span:
        yield span


def record_usage(
    span: Span, response_model: str | None, input_tokens: int, output_tokens: int, finish: Sequence[str]
) -> None:
    span.set_attribute(ATTR["response_model"], response_model or "")
    span.set_attribute(ATTR["input_tokens"], int(input_tokens))
    span.set_attribute(ATTR["output_tokens"], int(output_tokens))
    span.set_attribute(ATTR["finish_reasons"], list(finish) or ["stop"])


@contextmanager
def tool_span(name: str, call_id: str) -> Iterator[Span]:
    with tracer().start_as_current_span(
        f"execute_tool {name}",
        kind=SpanKind.CLIENT,
        attributes={
            ATTR["operation"]: "execute_tool",
            ATTR["tool_name"]: name,
            ATTR["tool_call_id"]: call_id,
        },
    ) as span:
        yield span


@contextmanager
def gate_span() -> Iterator[Span]:
    with tracer().start_as_current_span(
        "readback_gate", kind=SpanKind.INTERNAL, attributes={ATTR["operation"]: "readback_gate"}
    ) as span:
        yield span


def fail(span: Span, reason: str) -> None:
    span.set_status(Status(StatusCode.ERROR, reason))
