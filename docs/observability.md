# Observability

Every turn is one OpenTelemetry trace that crosses the protocol boundary. The agent opens an
invoke_agent span, puts traceparent and tracestate into the metadata of every MCP request, and the
server's spans (the SDK's own, one per tools/call) are children of the agent's execute_tool spans.
The scorecard, the viewer on the site and the eval runner read the same spans from Parquet.

## The names in use

The GenAI semantic conventions were read on 2026-10-23, when they were still in development status
upstream. These are the exact names this build sets; a later revision of the conventions will not
change them here without a dated entry in DECISIONS.md.

| Span | Name | Attributes set |
|---|---|---|
| one per turn | `invoke_agent readback` | gen_ai.operation.name = invoke_agent, gen_ai.agent.name, gen_ai.conversation.id, gen_ai.provider.name, readback.router.reason, readback.prompt_hash, readback.family, readback.verdict, readback.redacted (counts only) |
| one per model call | `chat <model>` | gen_ai.operation.name = chat, gen_ai.provider.name, gen_ai.request.model, gen_ai.response.model, gen_ai.response.finish_reasons, gen_ai.usage.input_tokens, gen_ai.usage.output_tokens, readback.cassette (hit, miss or recorded), readback.cassette.digest |
| one per tool call | `execute_tool <tool>` | gen_ai.operation.name = execute_tool, gen_ai.tool.name, gen_ai.tool.call.id |
| the server's, one per request | `tools/call <tool>` | mcp.method.name, mcp.protocol.version, gen_ai.operation.name = execute_tool, gen_ai.tool.name (set by the MCP SDK) |
| the gate | `readback_gate` | readback.gate.verdict, readback.gate.claims, readback.gate.unsupported, readback.gate.readback_calls |

## What is never captured

Message content is not captured. The content attributes of the conventions (gen_ai.input.messages,
gen_ai.output.messages, gen_ai.system_instructions) are never set, and tests/tracing/test_spans.py
reads every attribute of every span of a turn for the question text and fails if it finds it. The
redaction middleware records how many items it removed, never what they were.

## Where spans go

- **Parquet**, always: packages/tracing keeps finished spans in memory and writes
  results/traces/<run>.parquet, one row per span: trace id, span id, parent id, name, kind, start
  and end in nanoseconds, status, and the attributes as a struct of strings.
- **The answer log**: the live API writes each turn's spans to the readback.spans table, kept for
  seven days.
- **OTLP**, only when OTEL_EXPORTER_OTLP_ENDPOINT is set, which it is not by default. No vendor is
  involved unless someone sets it.

## Resuming a turn

A turn that resumes from a checkpoint, after an interrupt or after the process stopped, continues
the trace it started in: the turn stores its traceparent in the checkpoint and the resumed span is
opened under it. The result handles run_sql minted are bound to the trace id, so a resumed turn
that started a new trace would find its own evidence refused. The first version did exactly that,
and the crash test caught it.
