"""The graph: interrupt and resume, a crash between act and gate, the ceiling, summarization,
redaction, the repair path, and the floor on the development split."""

from __future__ import annotations

from typing import Any

from mcp import Client
from readback_agent.graph import _condense
from readback_agent.run import Agent
from readback_core.answer import Draft
from tests.fakes import Scripted, call

SQL = "select payment_share from mart_metro_year where cbsa_title = 'Denver-Aurora-Centennial, CO' and year = 2024"


def good_draft(display: str = "40.4%", value: float = 40.4, extra: str = "") -> dict[str, Any]:
    return Draft(text=f"The payment share in Denver in 2024 was {display}.{extra}",
                 claims=[{"value": value, "unit": "percent", "display": display, "warehouse": "doorstep", "result_id": "r1", "column": "payment_share"}]).model_dump()


async def test_the_floor_answers_a_lookup_with_its_readback(client: Client) -> None:
    t = await Agent().ask(client, "What was the payment share in Denver in 2024?", provider="floor")
    assert t.answer and t.answer.verdict == "verified" and t.answer.provider == "floor"
    assert [c.verdict for c in t.answer.claims] == ["agree"] and t.answer.claims[0].span is not None


async def test_the_interrupt_pauses_and_resumes_from_the_checkpoint(client: Client) -> None:
    agent = Agent()
    t = await agent.ask(client, "What was the payment share in Portland in 2019?", provider="floor")
    assert t.answer is None and t.interrupt and len(t.interrupt["candidates"]) == 2
    done = await agent.ask(client, "", thread_id=t.thread_id, provider="floor", resume=t.interrupt["candidates"][0])
    assert done.answer and done.answer.verdict == "verified" and "Portland-Vancouver" in done.answer.text


async def test_a_crash_between_act_and_gate_resumes(client: Client) -> None:
    agent = Agent()
    try:
        await agent.ask(client, "What was the payment share in Denver in 2024?", provider="floor", thread_id="crash", fail_gate_once=True)
    except RuntimeError as err:
        assert "between act and gate" in str(err)
    state = await agent.app.aget_state({"configurable": {"thread_id": "crash"}})
    assert state.next == ("gate",) and state.values["draft"]
    resumed = await agent.resume_after_crash(client, "crash", provider="floor")
    assert resumed.answer and resumed.answer.verdict == "verified"


async def test_the_ceiling_refuses_the_call_past_it(client: Client) -> None:
    agent = Agent(ceiling=1)
    t = await agent.ask(client, "Which carrier had the higher on time rate in 2019, Delta or United?", provider="floor")
    assert t.answer and t.answer.verdict == "refused" and "too wide" in (t.answer.refusal_reason or "")


async def test_a_refusal_calls_no_warehouse_tool(client: Client) -> None:
    t = await Agent().ask(client, "Should I buy a home in Austin or keep renting?", provider="floor")
    assert t.answer and t.answer.verdict == "refused" and t.answer.tools_called == []


def test_summarization_fires_past_the_threshold_and_is_labeled() -> None:
    history = [{"q": f"question {i} " * 40, "a": f"Answer {i}. More words here. " * 30} for i in range(6)]
    messages, summary = _condense(history, 200)
    assert summary and summary.startswith("Summary of earlier turns") and len(messages) == 3
    short, none = _condense(history[:1], 200)
    assert none is None and len(short) == 2


async def test_a_model_answer_is_read_back_and_shipped(client: Client, scripted_agent: Any) -> None:
    fake = Scripted(turns=[call("run_sql", {"warehouse": "doorstep", "sql": SQL}, 1)], answers=[good_draft()])
    t = await scripted_agent(fake).ask(client, "What was the payment share in Denver in 2024?", provider="groq")
    assert t.answer and t.answer.verdict == "verified" and t.answer.provider == "groq"
    assert t.answer.claims[0].result_id == "r1" and t.answer.claims[0].verdict == "agree"
    # the tool call, the turn that stops calling tools, and the structured answer
    assert t.answer.tokens_in > 0 and t.answer.model_calls == 3


async def test_redaction_removes_a_planted_email_phone_and_id_before_the_model(client: Client, scripted_agent: Any) -> None:
    fake = Scripted(turns=[call("run_sql", {"warehouse": "doorstep", "sql": SQL}, 1)], answers=[good_draft()])
    q = "I am jane.roe@gmail.com, 201-555-0143, account 88812345. What was the payment share in Denver in 2024?"
    t = await scripted_agent(fake).ask(client, q, provider="groq")
    sent = " ".join(str(m.content) for batch in fake.seen for m in batch)
    for planted in ("jane.roe@gmail.com", "201-555-0143", "88812345"):
        assert planted not in sent and planted not in (t.answer.question if t.answer else "")
    assert t.redactions == {"email": 1, "phone": 1, "identifier": 1}


async def test_an_unsupported_number_is_caught_repaired_once_and_labeled(client: Client, scripted_agent: Any) -> None:
    fake = Scripted(turns=[call("run_sql", {"warehouse": "doorstep", "sql": SQL}, 1)],
                    answers=[good_draft(extra=" It was 31.2% in 2019."), good_draft()])
    t = await scripted_agent(fake).ask(client, "What was the payment share in Denver in 2024?", provider="groq")
    assert t.answer and t.answer.verdict == "repaired"
    assert t.answer.gate.unsupported_before == 1 and any("31.2%" in c for c in t.answer.gate.caught)
    assert "31.2%" in (t.answer.gate.first_draft or "")


async def test_a_second_failure_refuses(client: Client, scripted_agent: Any) -> None:
    wrong = good_draft(display="45.0%", value=45.0)
    fake = Scripted(turns=[call("run_sql", {"warehouse": "doorstep", "sql": SQL}, 1)], answers=[wrong, wrong])
    t = await scripted_agent(fake).ask(client, "What was the payment share in Denver in 2024?", provider="groq")
    assert t.answer and t.answer.verdict == "refused" and "did not pass the gate" in (t.answer.refusal_reason or "")


async def test_every_claim_was_re_run(client: Client) -> None:
    t = await Agent().ask(client, "Among carriers that flew at least half a million flights in 2025, which 3 had the highest on time performance?", provider="floor")
    assert t.answer and t.answer.verdict == "verified"
    assert t.answer.gate.readback_calls == len(t.answer.claims) == t.answer.tools_called.count("readback")
