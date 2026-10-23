"""The API over real HTTP: the answer observed from an independent connection, the audit row before
the final event, both transports answering the same list, the version error, and the statement."""

from __future__ import annotations

import json
from typing import Any

import httpx
import sqlalchemy as sa
from mcp import Client
from readback_core.statements import STATEMENT
from readback_mcp_server.server import build_server

META = {
    "io.modelcontextprotocol/protocolVersion": "2026-07-28",
    "io.modelcontextprotocol/clientCapabilities": {},
}


def chat_events(url: str, question: str, on_event: Any = None) -> list[dict[str, Any]]:
    out = []
    with httpx.stream("POST", f"{url}/v1/chat", json={"question": question}, timeout=120) as r:
        kind = None
        for line in r.iter_lines():
            if line.startswith("event:"):
                kind = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                event = json.loads(line[5:])
                event["kind"] = kind
                if on_event:
                    on_event(event)
                out.append(event)
    return out


def test_answer_is_committed(live: dict[str, Any]) -> None:
    events = chat_events(str(live["url"]), "What was the payment share in Denver in 2024?")
    answer = next(e for e in events if e["kind"] == "answer")
    independent = sa.create_engine(f"sqlite+pysqlite:///{live['db']}")
    with independent.connect() as conn:
        row = conn.execute(
            sa.text("select verdict, trace_id, question from answers where id = :i"),
            {"i": answer["answer_id"]},
        ).first()
    assert row is not None and row[0] == "verified" and row[1] == answer["trace_id"]
    stored = httpx.get(f"{live['url']}/v1/answers/{answer['answer_id']}").json()
    assert stored["trace_id"] == answer["trace_id"] and stored["statement"] == STATEMENT
    spans = httpx.get(f"{live['url']}/v1/traces/{answer['trace_id']}").json()["spans"]
    assert any(s["name"] == "invoke_agent readback" for s in spans)


def test_audit_precedes_final_event(live: dict[str, Any]) -> None:
    independent = sa.create_engine(f"sqlite+pysqlite:///{live['db']}")
    seen: list[bool] = []

    def check(event: dict[str, Any]) -> None:
        if event["kind"] == "answer":
            with independent.connect() as conn:
                seen.append(
                    conn.execute(
                        sa.text("select count(*) from answers where id = :i"), {"i": event["answer_id"]}
                    ).scalar()
                    == 1
                )

    chat_events(str(live["url"]), "What was Delta's on time rate in 2019?", check)
    assert seen == [True]


def test_the_stream_carries_classification_tools_gate_and_answer(live: dict[str, Any]) -> None:
    kinds = [
        e["kind"]
        for e in chat_events(
            str(live["url"]), "What was the net interest margin at Harborline Bank in 2024Q4?"
        )
    ]
    assert (
        kinds[0] == "classified" and "tool" in kinds and "gate" in kinds and kinds[-2:] == ["answer", "done"]
    )


async def test_streamable_http_and_in_memory_answer_the_same_list(live: dict[str, Any]) -> None:
    async with Client(f"{live['url']}/mcp") as over_http:
        a = await over_http.list_tools(cache_mode="refresh")
    async with Client(build_server()) as in_memory:
        b = await in_memory.list_tools(cache_mode="refresh")
    assert [t.model_dump() for t in a.tools] == [t.model_dump() for t in b.tools]


def test_an_unsupported_protocol_version_gets_the_version_error(live: dict[str, Any]) -> None:
    meta = {**META, "io.modelcontextprotocol/protocolVersion": "1999-01-01"}
    r = httpx.post(
        f"{live['url']}/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {"_meta": meta}},
        headers={
            "accept": "application/json, text/event-stream",
            "mcp-protocol-version": "1999-01-01",
            "mcp-method": "tools/list",
        },
    )
    body = r.json()
    assert body["error"]["code"] == -32022 and "2026-07-28" in body["error"]["data"]["supported"]


def test_a_client_past_the_hour_is_refused(live: dict[str, Any]) -> None:
    body = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {"_meta": META}}
    headers = {
        "accept": "application/json, text/event-stream",
        "mcp-protocol-version": "2026-07-28",
        "mcp-method": "tools/list",
        "x-forwarded-for": "203.0.113.77",
    }
    codes = [httpx.post(f"{live['url']}/mcp", json=body, headers=headers).status_code for _ in range(61)]
    assert codes[:60] == [200] * 60 and codes[60] == 429


def test_health_carries_the_revision_the_pick_and_the_statement(live: dict[str, Any]) -> None:
    h = httpx.get(f"{live['url']}/health").json()
    assert h["protocol_revision"] == "2026-07-28" and h["statement"] == STATEMENT and h["database"] == "ok"
    assert h["budgets"][-1]["provider"] == "floor"
