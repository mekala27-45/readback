"""The agent: a LangGraph StateGraph with named nodes, because every edge is a decision.

    classify   the deterministic rules first (refusals, family, measure); the model only when the
               rules do not place the question; out of scope goes to refuse with no tool called
    plan       the tools to call, in order: the floor's compiled plan, or the family's template
    act        the tool loop over the MCP client, at most the ceiling of calls; every result kept
    interrupt  a lookup that needs a choice pauses the graph; the person chooses; it resumes
    gate       every claim read back through the readback tool; every number covered or exempt
    repair     one retry with the gate's report in context; a second failure refuses
    refuse     the stated refusal, labeled, with the reason
    answer     the Answer: text, claims with spans and verdicts, provider, model, tokens, trace id

Middleware, in the LangChain sense, sits on the act node: redaction before anything (the question
in state is already redacted), the budget before each model call (and the switch to the next
provider at the cap, recorded in the trace), summarization of older turns past a token length, and
the tool call ceiling. The state is checkpointed after every node, so a turn resumes after a crash
or an interrupt from where it stopped.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal, TypedDict

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
    message_to_dict,
    messages_from_dict,
)
from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from langgraph.types import interrupt
from opentelemetry import trace
from pydantic import ValidationError
from readback_core.answer import Answer, Choice, Draft, GateSummary, ShippedClaim
from readback_core.statements import REFUSAL
from readback_gate.gate import check_text, verify
from readback_planner.classify import Classification, classify
from readback_planner.floor import Floor
from readback_providers.cassettes import CassetteMiss
from readback_providers.ledger import BudgetSpent
from readback_providers.models import ModelCaller
from readback_providers.router import Router
from readback_tracing import fail, gate_span

from readback_agent.client import ToolClient, ToolError
from readback_agent.prompts import Registry

CEILING = 8
SUMMARIZE_AFTER_TOKENS = 1500
ROWS_SHOWN = 40
TOO_WIDE = "the question was too wide: it needed more than the tool call ceiling of {n} calls in one turn"
TEMPLATES: dict[str, list[str]] = {
    "lookup": ["lookup", "search_catalog", "describe", "run_sql", "readback"],
    "comparison": ["lookup", "search_catalog", "run_sql", "run_sql", "readback"],
    "trend": ["lookup", "search_catalog", "run_sql", "readback"],
    "top_k": ["search_catalog", "describe", "run_sql", "readback"],
    "definition": ["search_catalog", "readback"],
    "multi": ["warehouses", "run_sql", "readback"],
    "unknown": ["search_catalog", "describe", "run_sql", "readback"],
}


class State(TypedDict, total=False):
    question: str
    thread_id: str
    provider: str
    model: str
    family: str
    warehouses: list[str]
    rule: str
    refusal: str | None
    plan: list[str]
    messages: list[dict[str, Any]]
    history: list[dict[str, str]]
    summary: str | None
    draft: dict[str, Any] | None
    first_draft: dict[str, Any] | None
    aliases: dict[str, str]
    attempts: int
    needs_choice: dict[str, Any] | None
    choice: str | None
    gate: dict[str, Any] | None
    caught: list[str]
    unsupported_before: int
    parse_repairs: int
    answer: dict[str, Any] | None
    started: float
    traceparent: dict[str, str]


@dataclass
class Context:
    tools: ToolClient
    router: Router
    make_caller: Callable[[Any], ModelCaller]
    registry: Registry
    floor: Floor
    specs: list[dict[str, Any]]
    identifiers: set[str] = field(default_factory=set)
    ceiling: int = CEILING
    summarize_after: int = SUMMARIZE_AFTER_TOKENS
    fail_gate_once: list[bool] = field(default_factory=list)  # a test kills the graph between act and gate
    callers: dict[str, ModelCaller] = field(default_factory=dict)

    def caller(self, provider: Any) -> ModelCaller:
        if provider.name not in self.callers:
            self.callers[provider.name] = self.make_caller(provider)
        return self.callers[provider.name]


def _span(name: str, value: Any) -> None:
    trace.get_current_span().set_attribute(name, value)


# classify and plan


async def classify_node(state: State, runtime: Runtime[Context]) -> State:
    ctx = runtime.context
    c: Classification = classify(state["question"], ctx.floor.measures)
    _span("readback.family", c.family)
    out: State = {"family": c.family, "warehouses": c.warehouses, "rule": c.rule, "refusal": c.refusal}
    if c.family == "unknown" and state.get("provider") == "floor":
        out["refusal"] = "it is not a family the floor was written for, and no model is available"
    return out


def after_classify(state: State) -> Literal["refuse", "plan"]:
    return "refuse" if state.get("refusal") else "plan"


async def plan_node(state: State, runtime: Runtime[Context]) -> State:
    return {"plan": TEMPLATES.get(state.get("family", "unknown"), TEMPLATES["unknown"])}


# act


def _model_view(result: dict[str, Any], aliases: dict[str, str]) -> str:
    """A tool result as the model sees it: no statement, no timings, result ids as short aliases."""
    view = {k: v for k, v in result.items() if k not in {"statement", "elapsed_ms", "digest"}}
    if "result_id" in view:
        alias = f"r{len(aliases) + 1}"
        aliases[alias] = str(view["result_id"])
        view["result_id"] = alias
    if isinstance(view.get("rows"), list) and len(view["rows"]) > ROWS_SHOWN:
        view["rows"] = view["rows"][:ROWS_SHOWN]
        view["rows_note"] = f"first {ROWS_SHOWN} rows shown"
    return json.dumps(view, separators=(",", ":"), default=str)


def _condense(history: list[dict[str, str]], limit: int) -> tuple[list[BaseMessage], str | None]:
    """Older turns of a long thread are condensed to their first sentences, labeled as a summary."""
    messages: list[BaseMessage] = []
    size = sum(len(h["q"]) + len(h["a"]) for h in history) // 4
    if size <= limit or len(history) < 2:
        for h in history:
            messages += [HumanMessage(h["q"]), AIMessage(h["a"])]
        return messages, None
    older, recent = history[:-1], history[-1:]
    summary = "Summary of earlier turns in this thread: " + " ".join(
        f"Asked: {h['q']} Answered: {h['a'].split('. ')[0]}." for h in older
    )
    messages.append(SystemMessage(summary))
    for h in recent:
        messages += [HumanMessage(h["q"]), AIMessage(h["a"])]
    return messages, summary


async def act_node(state: State, runtime: Runtime[Context]) -> State:
    ctx = runtime.context
    ctx.tools.ceiling = ctx.ceiling
    if state.get("provider") == "floor":
        return await _act_floor(state, ctx)
    return await _act_model(state, ctx)


async def _act_floor(state: State, ctx: Context) -> State:
    try:
        result = await ctx.floor.answer(state["question"], choice=state.get("choice"))
    except ToolError as err:
        return {
            "refusal": TOO_WIDE.format(n=ctx.ceiling)
            if "ceiling" in err.message
            else f"a tool refused: {err.message}"
        }
    if result.needs_choice is not None and not state.get("choice"):
        return {"needs_choice": result.needs_choice.model_dump(), "plan": [s.tool for s in result.plan]}
    if result.draft.refused:
        return {
            "refusal": result.draft.refusal_reason or "the floor could not answer it",
            "plan": [s.tool for s in result.plan],
        }
    return {
        "draft": result.draft.model_dump(),
        "plan": [s.tool for s in result.plan],
        "needs_choice": None,
        "aliases": {},
    }


async def _act_model(state: State, ctx: Context) -> State:
    provider = next(p for p in ctx.router.providers if p.name == state["provider"])
    caller = ctx.caller(provider)
    aliases = dict(state.get("aliases") or {})
    if state.get("messages"):
        messages = messages_from_dict(state["messages"])
        if state.get("choice") and state.get("needs_choice"):
            pending = messages[-1]
            assert isinstance(pending, ToolMessage)
            messages[-1] = ToolMessage(
                json.dumps({"resolved": state["choice"], "chosen_by": "the person"}),
                tool_call_id=pending.tool_call_id,
            )
    else:
        history, summary = _condense(state.get("history") or [], ctx.summarize_after)
        if summary:
            _span("readback.summary", "extractive")
        plan = ", ".join(state.get("plan") or [])
        messages = [
            SystemMessage(ctx.registry.text("system")),
            *history,
            HumanMessage(f"{state['question']}\n\n(Suggested tools, in order: {plan}.)"),
        ]
    try:
        while True:
            ai = await caller(messages, ctx.specs)
            messages.append(ai)
            if not ai.tool_calls:
                break
            for call in ai.tool_calls:
                args = _resolve_aliases(call["args"], aliases)
                try:
                    result = await ctx.tools.call(call["name"], args)
                except ToolError as err:
                    if "ceiling" in err.message:
                        return {"refusal": TOO_WIDE.format(n=ctx.ceiling), "aliases": aliases}
                    messages.append(ToolMessage(json.dumps({"error": err.message}), tool_call_id=call["id"]))
                    continue
                messages.append(ToolMessage(_model_view(result, aliases), tool_call_id=call["id"]))
                if call["name"] == "lookup" and result.get("needs_choice"):
                    choice = Choice(
                        kind=result["kind"],
                        name=result["query"],
                        candidates=[c["value"] for c in result["candidates"]],
                    )
                    return {
                        "needs_choice": choice.model_dump(),
                        "messages": [message_to_dict(m) for m in messages],
                        "aliases": aliases,
                    }
        draft = await _submit(caller, messages, ctx, state)
    except BudgetSpent:
        return await _switch(state, ctx)
    except CassetteMiss as miss:
        _span("readback.cassette.miss", miss.digest)
        raise
    if draft is None:
        return {
            "refusal": "the model did not produce a valid structured answer after one repair",
            "aliases": aliases,
            "messages": [message_to_dict(m) for m in messages],
        }
    if draft.refused:
        return {"refusal": draft.refusal_reason or "the model refused", "aliases": aliases}
    return {
        "draft": draft.model_dump(),
        "messages": [message_to_dict(m) for m in messages],
        "aliases": aliases,
        "needs_choice": None,
    }


async def _submit(
    caller: ModelCaller, messages: list[BaseMessage], ctx: Context, state: State
) -> Draft | None:
    """The structured answer, with one parse and repair step."""
    ask = HumanMessage(ctx.registry.text("submit_answer"))
    error: str | None = None
    for attempt in range(2):
        prompt = (
            [*messages, ask]
            if error is None
            else [*messages, ask, HumanMessage(f"That answer did not parse: {error}. Submit it again.")]
        )
        raw = await caller.structured(prompt, Draft)
        try:
            return Draft.model_validate(raw)
        except ValidationError as err:
            error = str(err).splitlines()[0][:300]
            _span(f"readback.parse_repair.{attempt}", error)
    return None


async def _switch(state: State, ctx: Context) -> State:
    """The budget middleware: at the cap, the next eligible provider takes the turn."""
    choice = ctx.router.choose(exclude=(state["provider"],))
    _span(
        "readback.provider.switch",
        f"{state['provider']} to {choice.provider.name}: the day's budget is spent",
    )
    new: State = {
        **state,
        "provider": choice.provider.name,
        "model": choice.provider.model_id(),
        "messages": [],
        "aliases": {},
    }
    if choice.provider.is_floor:
        return {**(await _act_floor(new, ctx)), "provider": "floor", "model": "no model"}
    out = await _act_model(new, ctx)
    return {**out, "provider": choice.provider.name, "model": choice.provider.model_id()}


def _resolve_aliases(args: dict[str, Any], aliases: dict[str, str]) -> dict[str, Any]:
    out: dict[str, Any] = json.loads(json.dumps(args))
    claim = out.get("claim")
    if isinstance(claim, dict) and claim.get("result_id") in aliases:
        claim["result_id"] = aliases[claim["result_id"]]
    return out


def after_act(state: State) -> Literal["interrupt", "refuse", "gate"]:
    if state.get("needs_choice") and not state.get("choice"):
        return "interrupt"
    if state.get("refusal"):
        return "refuse"
    return "gate"


async def interrupt_node(state: State, runtime: Runtime[Context]) -> State:
    choice = interrupt(state["needs_choice"])
    return {"choice": str(choice)}


# gate and repair


async def gate_node(state: State, runtime: Runtime[Context]) -> State:
    ctx = runtime.context
    if ctx.fail_gate_once:
        ctx.fail_gate_once.pop()
        raise RuntimeError("the process stopped between act and gate")
    draft = Draft.model_validate(state["draft"])
    aliases = state.get("aliases") or {}
    with gate_span() as span:
        report = check_text(draft.text, [(c.display, c.value) for c in draft.claims], ctx.identifiers)

        async def readback(i: int) -> dict[str, Any]:
            claim = draft.claims[i].model_dump(exclude_none=True)
            if claim.get("result_id") in aliases:
                claim["result_id"] = aliases[claim["result_id"]]
            claim.pop("sql", None) if claim.get("result_id") else None
            try:
                return await ctx.tools.call("readback", {"claim": claim})
            except ToolError as err:
                return {"verdict": "refused", "reason": err.message}

        await verify(report, readback)
        span.set_attribute("readback.gate.verdict", "pass" if report.passed else "fail")
        span.set_attribute("readback.gate.claims", len(report.claims))
        span.set_attribute("readback.gate.unsupported", len(report.unsupported))
        span.set_attribute("readback.gate.readback_calls", report.readback_calls)
        if not report.passed:
            fail(span, "; ".join(report.failures())[:500])
    summary = {
        "passed": report.passed,
        "tokens": len(report.tokens),
        "exempt": len(report.exempt),
        "unsupported": len(report.unsupported),
        "readback_calls": report.readback_calls,
        "failures": report.failures(),
        "claims": [
            {
                "index": c.index,
                "span": c.span,
                "verdict": c.verdict,
                "reason": c.reason,
                "evidence": c.evidence,
                "tolerance": c.tolerance,
            }
            for c in report.claims
        ],
    }
    out: State = {"gate": summary}
    if state.get("attempts", 0) == 0:
        out["unsupported_before"] = len(report.unsupported)
        out["first_draft"] = state["draft"]
        if not report.passed:
            out["caught"] = report.failures()
    return out


def after_gate(state: State) -> Literal["answer", "repair", "refuse"]:
    gate = state.get("gate") or {}
    if gate.get("passed"):
        return "answer"
    if state.get("provider") != "floor" and state.get("attempts", 0) == 0:
        return "repair"
    return "refuse"


async def repair_node(state: State, runtime: Runtime[Context]) -> State:
    ctx = runtime.context
    messages = messages_from_dict(state.get("messages") or [])
    failures = "\n".join(f"- {f}" for f in (state.get("gate") or {}).get("failures", []))
    messages.append(HumanMessage(f"{ctx.registry.text('repair')}\n{failures}"))
    return {"messages": [message_to_dict(m) for m in messages], "attempts": 1, "draft": None, "refusal": None}


# endings


def _base(state: State, ctx: Context, verdict: str, text: str) -> dict[str, Any]:
    usage = ctx.callers[state["provider"]].usage if state.get("provider") in ctx.callers else None
    span = trace.get_current_span()
    return {
        "question": state["question"],
        "family": state.get("family", "unknown"),
        "text": text,
        "warehouses": state.get("warehouses") or [],
        "verdict": verdict,
        "provider": state.get("provider", "floor"),
        "model": state.get("model", "no model"),
        "tokens_in": usage.input_tokens if usage else 0,
        "tokens_out": usage.output_tokens if usage else 0,
        "model_calls": usage.calls if usage else 0,
        "latency_ms": round(max(0.0, time.time() - state.get("started", time.time())) * 1000, 1),
        "tool_calls": ctx.tools.calls,
        "tools_called": [r.tool for r in ctx.tools.records],
        "trace_id": format(span.get_span_context().trace_id, "032x"),
        "prompt_hash": ctx.registry.digest,
    }


async def refuse_node(state: State, runtime: Runtime[Context]) -> State:
    ctx = runtime.context
    reason = (
        state.get("refusal")
        or "the answer did not pass the gate after one repair: "
        + "; ".join((state.get("gate") or {}).get("failures", []))[:400]
    )
    text = f"{REFUSAL} This question was refused because {reason}."
    base = _base(state, ctx, "refused", text)
    gate = state.get("gate") or {}
    base["refusal_reason"] = reason
    base["gate"] = GateSummary(
        tokens=gate.get("tokens", 0),
        exempt=gate.get("exempt", 0),
        unsupported_before=state.get("unsupported_before", 0),
        unsupported_after=gate.get("unsupported", 0),
        readback_calls=gate.get("readback_calls", 0),
        caught=state.get("caught") or [],
        first_draft=(state.get("first_draft") or {}).get("text"),
    ).model_dump()
    return {"answer": Answer.model_validate(base).model_dump()}


async def answer_node(state: State, runtime: Runtime[Context]) -> State:
    ctx = runtime.context
    draft = Draft.model_validate(state["draft"])
    gate = state.get("gate") or {}
    checks = {c["index"]: c for c in gate.get("claims", [])}
    claims = []
    for i, c in enumerate(draft.claims):
        g = checks.get(i, {})
        claims.append(
            ShippedClaim(
                **c.model_dump(),
                span=tuple(g["span"]) if g.get("span") else None,
                verdict=g.get("verdict", "unchecked"),
                evidence=g.get("evidence"),
                tolerance=g.get("tolerance"),
                reason=g.get("reason", ""),
            )
        )
    verdict = "repaired" if state.get("attempts", 0) else "verified"
    base = _base(state, ctx, verdict, draft.text)
    base.update(
        claims=[c.model_dump() for c in claims],
        warehouses=draft.warehouses or state.get("warehouses") or [],
        selection=draft.selection,
        direction=draft.direction,
        gate=GateSummary(
            tokens=gate.get("tokens", 0),
            exempt=gate.get("exempt", 0),
            unsupported_before=state.get("unsupported_before", 0),
            unsupported_after=gate.get("unsupported", 0),
            readback_calls=gate.get("readback_calls", 0),
            caught=state.get("caught") or [],
            first_draft=(state.get("first_draft") or {}).get("text") if state.get("attempts") else None,
        ).model_dump(),
    )
    return {"answer": Answer.model_validate(base).model_dump()}


def build() -> StateGraph[State, Context, State, State]:
    g: StateGraph[State, Context, State, State] = StateGraph(State, context_schema=Context)
    g.add_node("classify", classify_node)
    g.add_node("plan", plan_node)
    g.add_node("act", act_node)
    g.add_node("interrupt", interrupt_node)
    g.add_node("gate", gate_node)
    g.add_node("repair", repair_node)
    g.add_node("refuse", refuse_node)
    g.add_node("answer", answer_node)
    g.add_edge(START, "classify")
    g.add_conditional_edges("classify", after_classify, {"refuse": "refuse", "plan": "plan"})
    g.add_edge("plan", "act")
    g.add_conditional_edges("act", after_act, {"interrupt": "interrupt", "refuse": "refuse", "gate": "gate"})
    g.add_edge("interrupt", "act")
    g.add_conditional_edges("gate", after_gate, {"answer": "answer", "repair": "repair", "refuse": "refuse"})
    g.add_edge("repair", "act")
    g.add_edge("refuse", END)
    g.add_edge("answer", END)
    return g
