"""The readback gate: the three tests every gate has, one per exemption rule, and the verdict."""

from __future__ import annotations

from typing import Any

from hypothesis import given
from hypothesis import strategies as st

from readback_gate.compare import compare, display_step
from readback_gate.gate import check_text, tokens, verify


def test_a_supported_answer_passes() -> None:
    r = check_text("The payment share in Denver in 2024 was 40.4%.", [("40.4%", 40.4)])
    assert not r.unsupported and r.claims[0].span is not None
    assert [e.rule for e in r.exempt] == ["year"]


def test_a_planted_unsupported_number_is_caught() -> None:
    r = check_text("The payment share was 40.4%, up from 31.2%.", [("40.4%", 40.4)])
    assert [t.text for t in r.unsupported] == ["31.2%"]
    assert any("31.2%" in f for f in r.failures())


def test_an_answer_with_no_numbers_passes() -> None:
    r = check_text("doorstep defines the payment share as twelve payments over the median household income.", [])
    assert r.tokens == [] and r.passed


def test_the_year_rule_exempts_a_year_and_only_a_year() -> None:
    r = check_text("From 2019 to 2023 it rose; 2019% is not a year and $2019 is money.", [])
    rules = {(e.token.text, e.rule) for e in r.exempt}
    assert ("2019", "year") in rules and ("2023", "year") in rules
    assert {t.text for t in r.unsupported} == {"2019%", "$2019"}


def test_the_identifier_rule_exempts_codes_the_catalog_knows() -> None:
    r = check_text("CBSA 19740 and carrier 9E in 2024Q2, but 19741 is not known.", [], identifiers=["19740", "9E"])
    exempted = {e.token.text for e in r.exempt if e.rule == "identifier"}
    assert exempted == {"19740"}
    # A quarter and a carrier code with a digit are words, not numbers: no token comes from them.
    assert {t.text for t in r.tokens} == {"19740", "19741"}
    assert [t.text for t in r.unsupported] == ["19741"]


def test_the_ordinal_rule_exempts_the_numbers_of_a_list_the_answer_numbers() -> None:
    text = "The three highest:\n1. Los Angeles at 42.2%\n2. San Francisco at 41.0%\n3. San Diego at 37.1%"
    r = check_text(text, [("42.2%", 42.2), ("41.0%", 41.0), ("37.1%", 37.1)])
    assert sorted(e.token.text for e in r.exempt if e.rule == "ordinal") == ["1", "2", "3"]
    assert not r.unsupported


def test_the_list_count_rule_exempts_the_count_and_not_another_number() -> None:
    text = "These 3 metros:\n1. A at 1.0%\n2. B at 2.0%\n3. C at 3.0%\nand 4 others."
    r = check_text(text, [("1.0%", 1.0), ("2.0%", 2.0), ("3.0%", 3.0)])
    assert any(e.rule == "list count" and e.token.text == "3" for e in r.exempt)
    assert [t.text for t in r.unsupported] == ["4"]


def test_a_list_that_does_not_run_from_one_is_not_exempt() -> None:
    r = check_text("Items:\n2. first\n5. second", [])
    assert {t.text for t in r.unsupported} == {"2", "5"}


async def test_verify_reads_back_every_claim_and_counts_the_calls() -> None:
    r = check_text("It was 40.4% and $1,200.", [("40.4%", 40.4), ("$1,200", 1200.0)])

    async def readback(i: int) -> dict[str, Any]:
        return {"verdict": "agree" if i == 0 else "disagree", "reason": "x"}

    await verify(r, readback)
    assert r.readback_calls == 2 and not r.passed


def test_display_step_reads_the_rounding_a_claim_was_shown_at() -> None:
    assert display_step("26.5%", 26.5) == 0.1
    assert display_step("$329,620", 329620) == 1
    assert display_step("$13.7 million", 13.7) == 100_000.0
    assert display_step(None, 3.25) == 0.01


@given(st.floats(min_value=-1e6, max_value=1e6, allow_nan=False), st.floats(min_value=0, max_value=10, allow_nan=False))
def test_the_verdict_is_monotonic_in_tolerance(value: float, offset: float) -> None:
    tight = compare(value + offset, "count", value, "count", display="1", scale=0.25).verdict == "agree"
    loose = compare(value + offset, "count", value, "count", display="1", scale=1.0).verdict == "agree"
    assert loose or not tight


@given(st.floats(min_value=-1.0, max_value=1.0, allow_nan=False))
def test_the_readback_is_symmetric_in_unit_conversion(fraction: float) -> None:
    a = compare(round(fraction * 100, 1), "percent", fraction, "fraction", display=f"{fraction * 100:.1f}%")
    b = compare(round(fraction, 3), "fraction", fraction * 100, "percent", display=f"{fraction:.3f}")
    assert a.verdict == b.verdict == "agree"


def test_tokens_keep_their_sign_and_suffix() -> None:
    assert [t.text for t in tokens("-2.2 min, $1,234 and 5.60%")] == ["-2.2 min", "$1,234", "5.60%"]
