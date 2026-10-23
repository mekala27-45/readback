"""The comparison at the heart of the readback: a claimed value against the warehouse's value.

The claim is compared in its own unit, after the one conversion the catalog allows (a fraction and a
percent, or basis points). The tolerance is half a unit of a rounding:

  - against a manifest key, the published rounding of that value (pct1 is a tenth of a point);
  - against a query result, the display rounding of the claim itself (a claim shown as 26.5% is
    held to a twentieth of a point; one shown as 27% to half a point).

Two values whose units cannot be reconciled are not compared: the verdict is a unit mismatch, and
the gate treats it as a failure. Pure code, no model anywhere.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Literal

from readback_core.units import FRACTIONAL, UnitMismatch, convert

Verdict = Literal["agree", "disagree", "unit mismatch"]
# A number as people print it: optional sign and currency, thousands separators, decimals.
_NUMBER = re.compile(r"[-+]?\$?\s*\d[\d,]*(?:\.(\d+))?")
_SCALE_WORDS = {"thousand": 1e3, "k": 1e3, "million": 1e6, "m": 1e6, "billion": 1e9, "b": 1e9}


@dataclass(frozen=True)
class Comparison:
    verdict: Verdict
    claim: float
    evidence: float | None
    unit: str
    difference: float | None
    tolerance: float | None
    reason: str


def display_step(display: str | None, value: float) -> float:
    """The rounding step a claim was shown at, read from its display string (26.5% gives 0.1)."""
    text = display if display else repr(value)
    m = _NUMBER.search(text)
    if not m:
        return 1.0
    decimals = len(m.group(1) or "")
    step = 10.0 ** (-decimals)
    tail = text[m.end() :].strip().lower()
    word = tail.split()[0].rstrip(".,") if tail else ""
    if word in _SCALE_WORDS:
        step *= _SCALE_WORDS[word]
    return step


def compare(
    claim: float,
    claim_unit: str,
    evidence: float | None,
    evidence_unit: str,
    *,
    display: str | None = None,
    published_step: float | None = None,
    scale: float = 0.5,
) -> Comparison:
    """Compare a claim with its evidence. `scale` is the tolerance as a multiple of the step (0.5)."""
    if evidence is None or (isinstance(evidence, float) and not math.isfinite(evidence)):
        return Comparison("disagree", claim, None, claim_unit, None, None, "the evidence has no value")
    try:
        in_claim_unit = convert(float(evidence), evidence_unit, claim_unit)
    except UnitMismatch as err:
        return Comparison("unit mismatch", claim, float(evidence), claim_unit, None, None, str(err))
    if published_step is not None:
        try:
            step = abs(convert(published_step, evidence_unit, claim_unit))
        except UnitMismatch as err:  # pragma: no cover - the same pair converted above
            return Comparison("unit mismatch", claim, float(evidence), claim_unit, None, None, str(err))
        source = "the published rounding"
    else:
        step = display_step(display, claim)
        # A share held as a fraction but shown in percent rounds in percent: 26.5% is a step of 0.001.
        if claim_unit in FRACTIONAL and display and ("%" in display or "pts" in display or "percent" in display):
            step /= 100.0
        source = "the display rounding of the claim"
    tolerance = step * scale
    difference = abs(claim - in_claim_unit)
    # A float comparison at the boundary of a rounding is decided by a margin far below any step.
    ok = difference <= tolerance + 1e-9 * max(1.0, abs(in_claim_unit))
    reason = f"within {tolerance:g} {claim_unit} ({source})" if ok else f"off by {difference:g} {claim_unit}, more than {tolerance:g}"
    return Comparison("agree" if ok else "disagree", claim, in_claim_unit, claim_unit, difference, tolerance, reason)


def is_fractional(unit: str) -> bool:
    return unit in FRACTIONAL
