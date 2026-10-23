"""The graders on fixtures with known verdicts."""

from __future__ import annotations

from readback_core.answer import Answer, ShippedClaim
from readback_core.statements import REFUSAL
from readback_evals.golden import KnownClaim, Question
from readback_evals.graders import grade


def answer(text: str, claims: list[tuple[float, str, str]] = (), **kw) -> Answer:  # type: ignore[assignment,no-untyped-def]
    return Answer(
        question="q",
        family="x",
        text=text,
        verdict=kw.pop("verdict", "verified"),
        provider="floor",
        model="no model",
        claims=[ShippedClaim(value=v, unit=u, display=d) for v, u, d in claims],
        **kw,
    )


def known(
    value: float, unit: str = "fraction", fmt: str = "pct1", tol: float = 0.0005, label: str = "a"
) -> KnownClaim:
    return KnownClaim(value=value, unit=unit, fmt=fmt, tolerance=tol, label=label)


def q(family: str, **kw) -> Question:  # type: ignore[no-untyped-def]
    return Question(id="X", family=family, warehouses=["doorstep"], question="q", split="test", **kw)


def test_lookup_passes_within_tolerance_in_another_unit_and_fails_outside() -> None:
    g = grade(q("lookup", claims=[known(0.40409)]), answer("40.4%", [(40.4, "percent", "40.4%")]))
    assert g.passed
    assert not grade(
        q("lookup", claims=[known(0.40409)]), answer("40.5%", [(40.5, "percent", "40.5%")])
    ).passed


def test_a_coarser_rounding_than_published_does_not_pass() -> None:
    assert not grade(q("lookup", claims=[known(0.2653)]), answer("27%", [(27.0, "percent", "27%")])).passed


def test_comparison_needs_the_winner_and_both_values() -> None:
    question = q("comparison", claims=[known(0.855, label="DL"), known(0.786, label="UA")], entity="DL")
    good = answer("Delta", [(85.5, "percent", "85.5%"), (78.6, "percent", "78.6%")], selection=["DL"])
    wrong = answer("United", [(85.5, "percent", "85.5%"), (78.6, "percent", "78.6%")], selection=["UA"])
    assert grade(question, good).passed and not grade(question, wrong).passed


def test_trend_needs_the_direction() -> None:
    question = q("trend", claims=[known(0.199), known(0.193)], direction="fell")
    assert grade(
        question,
        answer("It fell.", [(19.9, "percent", "19.9%"), (19.3, "percent", "19.3%")], direction="fell"),
    ).passed
    assert not grade(
        question,
        answer("It rose.", [(19.9, "percent", "19.9%"), (19.3, "percent", "19.3%")], direction="rose"),
    ).passed


def test_top_k_is_exact_order_with_jaccard_beside_it() -> None:
    question = q("top_k", ranking=["A", "B", "C"])
    exact = grade(question, answer("x", selection=["A", "B", "C"]))
    swapped = grade(question, answer("x", selection=["B", "A", "C"]))
    assert exact.passed and exact.jaccard == 1.0
    assert not swapped.passed and swapped.jaccard == 1.0


def test_definition_needs_every_key_phrase() -> None:
    question = q("definition", key_phrases=["twelve payments", "median household income"])
    assert grade(question, answer("Twelve payments over the median household income.")).passed
    assert not grade(question, answer("Twelve payments over income.")).passed


def test_refusal_is_a_hard_pass_or_fail() -> None:
    question = q("refusal", refuse=True)
    assert grade(question, answer(REFUSAL, verdict="refused")).passed
    assert not grade(question, answer(REFUSAL, verdict="refused", tools_called=["run_sql"])).passed
    assert not grade(question, answer("Buy in Austin.")).passed


def test_an_in_scope_question_refused_fails() -> None:
    assert not grade(q("lookup", claims=[known(0.4)]), answer(REFUSAL, verdict="refused")).passed
