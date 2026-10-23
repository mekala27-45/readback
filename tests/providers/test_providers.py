"""Budgets, the router, the ledger's shared transaction, and the cassettes."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest
from langchain_core.messages import HumanMessage, SystemMessage
from hypothesis import given, settings
from hypothesis import strategies as st

from readback_providers import registry
from readback_providers.cassettes import CassetteMiss, Store, request_digest
from readback_providers.ledger import BudgetSpent, Ledger, pacific_day
from readback_providers.models import ModelCaller
from readback_providers.router import Router
from tests.fakes import Scripted


def providers():  # type: ignore[no-untyped-def]
    return registry.load()


def test_the_floor_is_last_and_every_provider_allows_the_data() -> None:
    ps = providers()
    assert ps[-1].name == "floor" and [p.name for p in ps][:4] == ["gemini", "groq", "openrouter", "sambanova"]


def test_the_budget_refuses_at_the_cap_and_the_router_tries_the_next(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    monkeypatch.setenv("GROQ_API_KEY", "y")
    ledger = Ledger.memory()
    router = Router(providers(), ledger)
    assert router.choose().provider.name == "gemini"
    gemini = providers()[0]
    for i in range(gemini.daily_budget or 0):
        ledger.reserve("gemini", "m", gemini.daily_budget or 0, f"d{i}", "t")
    with pytest.raises(BudgetSpent):
        ledger.reserve("gemini", "m", gemini.daily_budget or 0, "over", "t")
    choice = router.choose()
    assert choice.provider.name == "groq" and ("gemini", "the day's budget is spent") in choice.skipped


def test_with_no_key_the_router_picks_the_floor(monkeypatch: pytest.MonkeyPatch) -> None:
    for p in providers():
        if p.key_env:
            monkeypatch.delenv(p.key_env, raising=False)
    assert Router(providers(), Ledger.memory()).choose().provider.name == "floor"


def test_the_ledger_row_and_the_audit_row_share_a_transaction() -> None:
    ledger = Ledger.memory()

    def boom() -> None:
        raise RuntimeError("the process stopped between the two rows")

    with pytest.raises(RuntimeError):
        ledger.reserve("groq", "m", 10, "d", "t", fail_between=boom)
    assert ledger.used("groq") == 0 and ledger.audit_rows() == 0
    ledger.reserve("groq", "m", 10, "d", "t")
    assert ledger.used("groq") == 1 and ledger.audit_rows() == 1


def test_the_day_is_the_pacific_day() -> None:
    late = dt.datetime(2026, 10, 24, 5, 0, tzinfo=dt.UTC)  # 22:00 on the 23rd in Los Angeles
    assert pacific_day(late) == dt.date(2026, 10, 23)


@settings(max_examples=25, deadline=None)
@given(st.integers(min_value=1, max_value=12), st.integers(min_value=0, max_value=30))
def test_the_budget_never_goes_negative(cap: int, attempts: int) -> None:
    ledger = Ledger.memory()
    for i in range(attempts):
        try:
            ledger.reserve("p", "m", cap, str(i), "t")
        except BudgetSpent:
            pass
    assert 0 <= ledger.used("p") <= cap and ledger.remaining("p", cap) >= 0


@settings(max_examples=25, deadline=None)
@given(st.integers(min_value=0, max_value=5))
def test_the_choice_of_the_router_is_stable_under_a_fixed_ledger(spent: int) -> None:
    ledger = Ledger.memory()
    for i in range(spent):
        ledger.reserve("gemini", "m", 100, str(i), "t")
    r = Router(providers(), ledger)
    assert r.choose().provider.name == r.choose().provider.name


def test_a_changed_prompt_changes_the_digest() -> None:
    a = request_digest("groq", "m", "h", [SystemMessage("You answer."), HumanMessage("q")])
    b = request_digest("groq", "m", "h", [SystemMessage("You answer!"), HumanMessage("q")])
    c = request_digest("groq", "m", "h2", [SystemMessage("You answer."), HumanMessage("q")])
    assert len({a, b, c}) == 3


async def test_a_cassette_records_then_replays_and_a_miss_fails_with_the_digest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    groq = next(p for p in providers() if p.name == "groq")
    ledger = Ledger.memory()
    store = Store(tmp_path)
    fake = Scripted(turns=[])
    caller = ModelCaller(groq, ledger, store, "h", "t", factory=lambda p: fake)
    messages = [SystemMessage("s"), HumanMessage("q")]
    monkeypatch.setenv("READBACK_CASSETTES", "record")
    first = await caller(messages, [])
    assert ledger.used("groq") == 1 and len(list(tmp_path.rglob("*.json"))) == 1
    monkeypatch.setenv("READBACK_CASSETTES", "replay")
    again = await caller(messages, [])
    assert again.content == first.content and ledger.used("groq") == 1 and store.hits == 1
    with pytest.raises(CassetteMiss) as miss:
        await caller([SystemMessage("s"), HumanMessage("another")], [])
    assert len(miss.value.digest) == 64 and miss.value.digest in str(miss.value)


async def test_each_structured_mode_parses_its_fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from readback_core.answer import Draft

    monkeypatch.setenv("READBACK_CASSETTES", "record")
    for name in ("gemini", "openrouter"):  # schema mode and the tool calling strategy
        p = next(x for x in providers() if x.name == name)
        fake = Scripted(answers=[{"text": "It was 40.4%.", "claims": []}])
        caller = ModelCaller(p, Ledger.memory(), Store(tmp_path), "h", "t", factory=lambda _p, f=fake: f)
        out = await caller.structured([HumanMessage("q")], Draft)
        assert out is not None and Draft.model_validate(out).text == "It was 40.4%."
