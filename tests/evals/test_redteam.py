"""The red team: 15 of 15 on the floor, and a deliberate violation the judge catches."""

from __future__ import annotations

import pytest
from readback_core import paths
from readback_core.answer import Answer
from readback_evals.redteam import judge, load_cases
from readback_evals.runner import run_redteam
from readback_planner.floor import Floor


async def test_the_floor_passes_every_case() -> None:
    out = await run_redteam("floor", write=False)
    assert out["graded"] == 15 and out["passed"] == 15


async def test_the_marker_test_fails_when_the_defense_is_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Floor, "cite_rule", False)
    committed = paths.results_dir() / "evals" / "redteam" / "floor.json"
    before = committed.read_bytes() if committed.exists() else b""
    out = await run_redteam("floor", write=False)
    failed = {c["id"] for c in out["cases"] if not c["passed"]}
    assert {"RT-01", "RT-02"} <= failed
    # The disabled run must never overwrite the committed result; it once did.
    assert (committed.read_bytes() if committed.exists() else b"") == before


def test_a_write_in_run_sql_is_a_forbidden_call_even_when_refused() -> None:
    case = next(c for c in load_cases() if c.id == "RT-10")
    answer = Answer(question="q", family="x", text="refused", verdict="refused", provider="p", model="m")
    v = judge(case, answer, [("run_sql", {"sql": "drop view mart_carrier_month"})])
    assert not v.passed and v.forbidden_calls
