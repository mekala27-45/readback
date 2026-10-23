"""Wilson, Benjamini-Hochberg and kappa on fixtures, and the scorecard reproduces from the runs."""

from __future__ import annotations

import json

from hypothesis import given
from hypothesis import strategies as st

from readback_core import paths
from readback_evals.scorecard import build
from readback_evals.stats import benjamini_hochberg, difference_interval, kappa, wilson


def test_wilson_on_a_textbook_case() -> None:
    low, high = wilson(98, 100)
    assert round(low, 4) == 0.93 and round(high, 4) == 0.9945


@given(st.integers(min_value=0, max_value=200), st.integers(min_value=1, max_value=200))
def test_the_wilson_interval_contains_the_point_estimate(k: int, n: int) -> None:
    k = min(k, n)
    low, high = wilson(k, n)
    assert low <= k / n <= high


def test_benjamini_hochberg_on_the_classic_fixture() -> None:
    p = [0.01, 0.04, 0.03, 0.005, 0.2]
    assert benjamini_hochberg(p, 0.05) == [True, True, True, True, False]
    assert benjamini_hochberg([0.5, 0.6], 0.05) == [False, False]


def test_a_difference_of_equal_proportions_straddles_zero() -> None:
    low, high, p = difference_interval(50, 100, 50, 100)
    assert low < 0 < high and p == 1.0


def test_kappa_is_one_for_agreement_and_zero_for_chance() -> None:
    assert kappa([True, False, True, False], [True, False, True, False]) == 1.0
    assert kappa([True, True, False, False], [True, False, True, False]) == 0.0


def test_the_scorecard_reproduces_from_the_runs() -> None:
    card = json.loads((paths.results_dir() / "evals/scorecard.json").read_text())
    again = json.loads(json.dumps(build(), sort_keys=True, default=str))
    assert again["test"] == card["test"] and again["default_provider"] == card["default_provider"]
