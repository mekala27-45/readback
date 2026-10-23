"""One turn of the agent: redact, route, run the graph, return the answer or the interrupt."""

from __future__ import annotations

import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from mcp import Client
from readback_core.answer import Answer
from readback_planner.floor import Floor
from readback_providers import registry as provider_registry
from readback_providers.cassettes import Store
from readback_providers.ledger import Ledger
from readback_providers.models import ModelCaller
from readback_providers.router import Router
from readback_tracing import agent_span, carrier, trace_id_of

from readback_agent.client import ToolClient
from readback_agent.graph import CEILING, SUMMARIZE_AFTER_TOKENS, Context, build
from readback_agent.prompts import Registry, registry
from readback_agent.redact import redact

_GRAPH: Any = None


@dataclass
class Turn:
    thread_id: str
    answer: Answer | None
    interrupt: dict[str, Any] | None
    trace_id: str
    redactions: dict[str, int] = field(default_factory=dict)
    provider_reason: str = ""


def graph(checkpointer: BaseCheckpointSaver[Any]) -> Any:
    return build().compile(checkpointer=checkpointer)


def submit_answer_spec(reg: Registry) -> dict[str, Any]:
    from readback_core.answer import Draft

    return {"type": "function", "function": {"name": "submit_answer", "description": reg.text("submit_answer").strip(), "parameters": Draft.model_json_schema()}}


async def tool_specs(client: Client) -> list[dict[str, Any]]:
    tools = (await client.list_tools()).tools
    return [{"type": "function", "function": {"name": t.name, "description": t.description or "", "parameters": t.input_schema}} for t in tools]


@dataclass
class Agent:
    """Everything a turn needs that outlives a turn: the ledger, the cassettes, the checkpointer."""

    ledger: Ledger = field(default_factory=Ledger.memory)
    store: Store = field(default_factory=Store)
    checkpointer: BaseCheckpointSaver[Any] = field(default_factory=InMemorySaver)
    providers: list[Any] = field(default_factory=provider_registry.load)
    ceiling: int = CEILING
    summarize_after: int = SUMMARIZE_AFTER_TOKENS
    model_factory: Any = None
    _identifiers: set[str] | None = None

    def __post_init__(self) -> None:
        self.app = graph(self.checkpointer)

    async def identifiers(self, tools: ToolClient) -> set[str]:
        if self._identifiers is None:
            out = await tools.call("run_sql", {"warehouse": "doorstep", "sql": "select distinct cbsa_code from mart_metro_year", "limit": 500})
            ids = {str(r[0]) for r in out["rows"]}
            more = await tools.call("run_sql", {"warehouse": "ledger", "sql": "select distinct cast(county_fips as varchar) from f03_county"})
            ids |= {str(r[0]) for r in more["rows"]}
            self._identifiers = ids
            await Floor(tools.call).dictionaries()
            tools.records.clear()  # the warm up is not part of any turn's count
        return self._identifiers

    async def stream(
        self,
        client: Client,
        question: str,
        *,
        thread_id: str | None = None,
        provider: str | None = None,
        resume: str | None = None,
        fail_gate_once: bool = False,
    ) -> AsyncIterator[dict[str, Any]]:
        """Run one turn and yield its events: classified, tool, gate, then interrupt or answer."""
        thread = thread_id or uuid.uuid4().hex
        config = {"configurable": {"thread_id": thread}}
        cleaned = redact(question)
        router = Router(self.providers, self.ledger, only=provider)
        choice = router.choose()
        reg = registry()
        tools = ToolClient(client)
        identifiers = await self.identifiers(tools)
        specs = await tool_specs(client)
        parent = None
        if resume is not None:
            saved = await self.app.aget_state(config)
            parent = (saved.values or {}).get("traceparent") if saved else None
        with agent_span(thread, parent=parent) as span:
            trace_id = trace_id_of(span)
            span.set_attribute("gen_ai.provider.name", choice.provider.name)
            span.set_attribute("readback.router.reason", choice.reason)
            span.set_attribute("readback.prompt_hash", reg.digest)
            if cleaned.removed:
                span.set_attribute("readback.redacted", ",".join(f"{k}:{v}" for k, v in sorted(cleaned.removed.items())))

            def make_caller(p: Any) -> ModelCaller:
                kwargs = {"factory": self.model_factory} if self.model_factory else {}
                return ModelCaller(p, self.ledger, self.store, reg.digest, trace_id, **kwargs)

            ctx = Context(tools=tools, router=router, make_caller=make_caller, registry=reg, floor=Floor(tools.call), specs=specs,
                          identifiers=identifiers, ceiling=self.ceiling, summarize_after=self.summarize_after,
                          fail_gate_once=[True] if fail_gate_once else [])
            if resume is not None:
                start: Any = Command(resume=resume)
            else:
                previous = await self.app.aget_state(config)
                history = list(previous.values.get("history") or []) if previous and previous.values else []
                last = previous.values.get("answer") if previous and previous.values else None
                if last:
                    history.append({"q": last["question"], "a": last["text"]})
                start = {
                    "question": cleaned.text, "thread_id": thread, "provider": choice.provider.name, "model": choice.provider.model_id(),
                    "history": history, "messages": [], "aliases": {}, "attempts": 0, "draft": None, "first_draft": None,
                    "gate": None, "needs_choice": None, "choice": None, "refusal": None, "caught": [], "answer": None,
                    "unsupported_before": 0, "started": time.perf_counter(), "traceparent": carrier(),
                }
            sent = 0
            meta = {"thread_id": thread, "trace_id": trace_id, "redactions": cleaned.removed}
            async for update in self.app.astream(start, config, context=ctx, stream_mode="updates"):
                for node, values in update.items():
                    while sent < len(tools.records):
                        r = tools.records[sent]
                        sent += 1
                        yield {"event": "tool", **meta, "id": r.id, "tool": r.tool, "ok": r.ok, "args": r.args,
                               "result_id": (r.result or {}).get("result_id"), "error": r.error}
                    if node == "classify" and values:
                        yield {"event": "classified", **meta, "family": values.get("family"), "rule": values.get("rule"),
                               "provider": choice.provider.name, "reason": choice.reason}
                    elif node == "gate" and values:
                        gate = values.get("gate") or {}
                        yield {"event": "gate", **meta, "passed": gate.get("passed"), "claims": gate.get("claims", []),
                               "unsupported": gate.get("unsupported", 0)}
                    elif node == "__interrupt__":
                        value = values[0].value if isinstance(values, (list, tuple)) else values
                        yield {"event": "interrupt", **meta, **dict(value)}
                        return
                    elif node in {"answer", "refuse"} and values:
                        answer = Answer.model_validate(values["answer"])
                        span.set_attribute("readback.verdict", answer.verdict)
                        yield {"event": "answer", **meta, "answer": answer.model_dump()}

    async def ask(self, client: Client, question: str, **kwargs: Any) -> Turn:
        answer: Answer | None = None
        interrupt_value: dict[str, Any] | None = None
        meta: dict[str, Any] = {}
        async for event in self.stream(client, question, **kwargs):
            meta = event
            if event["event"] == "answer":
                answer = Answer.model_validate(event["answer"])
            elif event["event"] == "interrupt":
                interrupt_value = {k: v for k, v in event.items() if k not in {"event", "thread_id", "trace_id", "redactions"}}
        return Turn(meta.get("thread_id", ""), answer, interrupt_value, meta.get("trace_id", ""), meta.get("redactions", {}))

    async def resume_after_crash(self, client: Client, thread_id: str, provider: str | None = None) -> Turn:
        """Continue a turn whose process stopped mid graph, from its last checkpoint."""
        config = {"configurable": {"thread_id": thread_id}}
        router = Router(self.providers, self.ledger, only=provider)
        reg = registry()
        tools = ToolClient(client)
        saved = await self.app.aget_state(config)
        parent = (saved.values or {}).get("traceparent") if saved else None
        with agent_span(thread_id, parent=parent) as span:
            ctx = Context(tools=tools, router=router, make_caller=lambda p: ModelCaller(p, self.ledger, self.store, reg.digest, trace_id_of(span)),
                          registry=reg, floor=Floor(tools.call), specs=await tool_specs(client), identifiers=await self.identifiers(tools))
            result = await self.app.ainvoke(None, config, context=ctx)
            return Turn(thread_id, Answer.model_validate(result["answer"]), None, trace_id_of(span))
