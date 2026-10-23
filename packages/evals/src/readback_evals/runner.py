"""The eval runner: every golden question through one provider, over the in memory MCP client.

The answers, the grades, the tool calls, the tokens and the latency are written to
results/evals/runs/<provider>.json and the spans to results/traces/<provider>.parquet. A provider in
replay mode whose cassette is missing for a question gets no grade for it: the scorecard states the
share graded and never extrapolates. The floor needs no cassette and is graded on every question.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict
from typing import Any

from mcp import Client
from readback_agent.run import Agent
from readback_core import paths
from readback_mcp_server.server import build_server
from readback_providers.cassettes import CassetteMiss
from readback_tracing import install

from readback_evals.golden import Question, load
from readback_evals.graders import grade
from readback_evals.redteam import RedTeamState, judge, load_cases


def _answer_row(q: Question, turn: Any, tool_args: list[tuple[str, dict[str, Any]]], seconds: float) -> dict[str, Any]:
    g = grade(q, turn.answer)
    a = turn.answer
    return {
        "id": q.id, "family": q.family, "split": q.split, "warehouses": q.warehouses, "graded": True,
        "passed": g.passed, "checks": g.checks, "jaccard": g.jaccard, "note": g.note,
        "verdict": a.verdict, "text": a.text, "selection": a.selection, "direction": a.direction,
        "claims": [{"display": c.display, "verdict": c.verdict, "value": c.value, "evidence": c.evidence, "tolerance": c.tolerance, "unit": c.unit,
                    "difference": None if c.evidence is None else abs(c.value - c.evidence)} for c in a.claims],
        "gate": a.gate.model_dump(), "tool_calls": a.tool_calls, "warehouse_calls": sum(t not in {"readback"} for t in a.tools_called),
        "tools_called": a.tools_called, "model_calls": a.model_calls, "tokens_in": a.tokens_in, "tokens_out": a.tokens_out,
        "latency_ms": round(seconds * 1000, 1), "trace_id": turn.trace_id, "model": a.model, "refusal_reason": a.refusal_reason,
        "tool_args": [[t, args] for t, args in tool_args],
    }


async def run_golden(provider: str, questions: list[Question] | None = None, agent: Agent | None = None) -> dict[str, Any]:
    exporter = install()
    exporter.clear()
    questions = questions or load(paths.evals_dir() / "golden")
    agent = agent or Agent()
    rows: list[dict[str, Any]] = []
    async with Client(build_server()) as client:
        for q in questions:
            started = time.perf_counter()
            records: list[tuple[str, dict[str, Any]]] = []
            try:
                turn = await _ask(agent, client, q.question, provider, records)
            except CassetteMiss as miss:
                rows.append({"id": q.id, "family": q.family, "split": q.split, "warehouses": q.warehouses, "graded": False,
                             "passed": False, "note": f"cassette miss {miss.digest[:12]}"})
                continue
            rows.append(_answer_row(q, turn, records, time.perf_counter() - started))
    out_dir = paths.results_dir() / "evals" / "runs"
    out_dir.mkdir(parents=True, exist_ok=True)
    from readback_agent.prompts import registry

    doc = {"provider": provider, "prompt_hash": registry().digest,
           "cassette_dates": agent.store.dates(provider) if provider != "floor" else [], "rows": rows}
    (out_dir / f"{provider}.json").write_text(json.dumps(doc, indent=1, sort_keys=True, default=str) + "\n", encoding="utf-8")
    exporter.write(paths.results_dir() / "traces" / f"{provider}.parquet")
    return doc


async def _ask(agent: Agent, client: Client, question: str, provider: str, records: list[tuple[str, dict[str, Any]]]) -> Any:
    """One turn, keeping every tool call with its arguments. An interrupt is answered with the first
    candidate; the golden questions name nothing ambiguous, so none should occur."""
    from readback_agent.run import Turn
    from readback_core.answer import Answer

    kwargs: dict[str, Any] = {"provider": provider}
    text = question
    for _ in range(3):
        answer = None
        meta: dict[str, Any] = {}
        pending = None
        async for event in agent.stream(client, text, **kwargs):
            meta = event
            if event["event"] == "tool":
                records.append((event["tool"], dict(event.get("args") or {})))
            elif event["event"] == "answer":
                answer = Answer.model_validate(event["answer"])
            elif event["event"] == "interrupt":
                pending = event
        if answer is not None:
            return Turn(meta["thread_id"], answer, None, meta["trace_id"], meta.get("redactions", {}))
        if pending is None:
            raise RuntimeError("the turn ended with neither an answer nor an interrupt")
        kwargs = {"provider": provider, "thread_id": pending["thread_id"], "resume": pending["candidates"][0]}
        text = ""
    raise RuntimeError("the turn asked for a choice three times")


async def run_redteam(provider: str, agent: Agent | None = None) -> dict[str, Any]:
    agent = agent or Agent()
    verdicts = []
    async with Client(build_server(RedTeamState())) as client:
        for case in load_cases():
            records: list[tuple[str, dict[str, Any]]] = []
            try:
                turn = await _ask(agent, client, case.question, provider, records)
            except CassetteMiss as miss:
                verdicts.append({"id": case.id, "kind": case.kind, "graded": False, "note": f"cassette miss {miss.digest[:12]}"})
                continue
            v = judge(case, turn.answer, records)
            verdicts.append({**asdict(v), "graded": True, "text": turn.answer.text[:400], "tools": [t for t, _ in records]})
    out = {"provider": provider, "cases": verdicts, "passed": sum(1 for v in verdicts if v.get("passed")), "graded": sum(1 for v in verdicts if v.get("graded"))}
    path = paths.results_dir() / "evals" / "redteam" / f"{provider}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=1, sort_keys=True, default=str) + "\n", encoding="utf-8")
    return out


def load_run(provider: str) -> dict[str, Any] | None:
    path = paths.results_dir() / "evals" / "runs" / f"{provider}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
