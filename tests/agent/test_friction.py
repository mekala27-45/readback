"""friction, the fourth warehouse: the floor answers its measures and its definitions with every number
read back. friction joined after the golden set was registered, so these questions are checked here
and graded nowhere; the known value of each is the measure's own SQL, run apart from the floor."""

from __future__ import annotations

import re

from mcp import Client
from readback_agent.run import Agent
from readback_catalog.measures import load, value_sql
from readback_core import paths
from readback_core.formats import format_value
from readback_warehouse.connection import Warehouse

MEASURES = {m.id: m for m in load(paths.root() / "catalog" / "measures.yaml") if m.warehouse == "friction"}


def known(measure: str, quarter: str) -> str:
    m = MEASURES[measure]
    value = Warehouse.shared().scalar(value_sql(m, None, quarter))
    return format_value(float(value), m.fmt)


QUESTIONS = {
    "fraud_capture": "What was the capture of fraud dollars at the friction payments desk in 2019Q4?",
    "step_up_rate": "What was the step up rate of good customers at friction in 2019Q4?",
    "decline_rate": "What was the decline rate of good customers at friction in 2019Q4?",
    "payment_decisions": "What was the number of payment decisions at friction in 2019Q4?",
}


async def test_the_floor_answers_each_friction_measure_with_its_readback(client: Client) -> None:
    agent = Agent()
    for measure, question in QUESTIONS.items():
        t = await agent.ask(client, question, provider="floor")
        assert t.answer and t.answer.verdict == "verified", (measure, t.answer)
        assert [c.verdict for c in t.answer.claims] == ["agree"]
        assert "friction payments desk" in t.answer.text
        assert known(measure, "2019Q4") in t.answer.text


async def test_a_rate_per_1000_is_said_per_1000_and_read_back_in_that_unit(client: Client) -> None:
    question = "What was the step up rate of good customers at friction in 2019Q4?"
    t = await Agent().ask(client, question, provider="floor")
    assert t.answer is not None
    claim = t.answer.claims[0]
    assert claim.unit == "per thousand" and claim.display.endswith(" per 1,000")
    assert re.search(r"\d per 1,000\.$", t.answer.text)


async def test_the_floor_quotes_friction_definitions_from_its_document(client: Client) -> None:
    t = await Agent().ask(client, "How does friction define a step up?", provider="floor")
    assert t.answer and t.answer.verdict == "verified"
    assert "one time code" in t.answer.text and "friction" in t.answer.text
