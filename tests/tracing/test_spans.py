"""One trace per turn across the protocol boundary, exported to Parquet, with no content captured."""

from __future__ import annotations

from pathlib import Path

import pyarrow.parquet as pq
from mcp import Client
from readback_agent.run import Agent
from readback_tracing import CONTENT_ATTRIBUTES

QUESTION = "Which carrier had the higher on time rate in 2019, Delta or United?"


async def test_one_invoke_agent_span_per_turn_with_tool_children(client: Client, exporter) -> None:  # type: ignore[no-untyped-def]
    t = await Agent().ask(client, QUESTION, provider="floor")
    rows = exporter.rows(t.trace_id)
    agents = [r for r in rows if r["name"] == "invoke_agent readback"]
    assert len(agents) == 1
    tools = [r for r in rows if r["name"].startswith("execute_tool ")]
    assert tools and all(r["trace_id"] == t.trace_id for r in rows)
    gate = [r for r in rows if r["name"] == "readback_gate"]
    assert len(gate) == 1 and gate[0]["attributes"]["readback.gate.verdict"] == "pass"


async def test_the_server_span_is_a_child_of_the_agents_tool_span(client: Client, exporter) -> None:  # type: ignore[no-untyped-def]
    t = await Agent().ask(client, QUESTION, provider="floor")
    rows = exporter.rows(t.trace_id)
    by_id = {r["span_id"]: r for r in rows}
    server = [r for r in rows if r["name"].startswith("tools/call ")]
    assert server
    for s in server:
        parent = by_id.get(s["parent_id"] or "")
        assert parent is not None and parent["name"] == f"execute_tool {s['name'].split(' ', 1)[1]}"


async def test_no_question_text_appears_in_any_span(client: Client, exporter) -> None:  # type: ignore[no-untyped-def]
    t = await Agent().ask(client, QUESTION, provider="floor")
    for r in exporter.rows(t.trace_id):
        assert not set(r["attributes"]) & set(CONTENT_ATTRIBUTES)
        for value in r["attributes"].values():
            assert "on time rate in 2019" not in str(value) and "Delta or United" not in str(value)


async def test_the_parquet_row_count_equals_the_span_count(client: Client, exporter, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    t = await Agent().ask(client, QUESTION, provider="floor")
    path = tmp_path / "trace.parquet"
    n = exporter.write(path, t.trace_id)
    table = pq.read_table(path)
    assert table.num_rows == n == len(exporter.rows(t.trace_id))
    assert set(table.column_names) >= {
        "trace_id",
        "span_id",
        "parent_id",
        "name",
        "start_ns",
        "end_ns",
        "attributes",
    }
