"""The graders, all code. A model never grades an answer.

Each family has its rule:
  lookup      every known value is in the answer, within its tolerance, in its unit;
  comparison  the named winner is the known one, and both values are there;
  trend       the direction matches the known sign, and both values are there;
  top_k       the known entities in the known order (exact), with Jaccard at k reported beside it;
  definition  every known key phrase is in the answer;
  multi       the known set of years, or the winner and its values, or the total;
  refusal     the stated refusal, and no warehouse tool called.

A value counts as present when a claim of the answer agrees with it after unit conversion, or, for
a count the gate exempts (the number of items in a list), when the text prints it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from readback_core.answer import Answer
from readback_core.statements import REFUSAL
from readback_core.units import UnitMismatch, convert
from readback_gate.gate import tokens

from readback_evals.golden import KnownClaim, Question

WAREHOUSE_TOOLS = {"describe", "search_catalog", "run_sql", "published", "lookup", "warehouses"}


@dataclass
class Grade:
    id: str
    family: str
    passed: bool
    checks: dict[str, bool] = field(default_factory=dict)
    jaccard: float | None = None
    note: str = ""


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9%]+", " ", text.lower()).strip()


def value_present(known: KnownClaim, answer: Answer) -> bool:
    for c in answer.claims:
        try:
            v = convert(c.value, c.unit, known.unit)
        except UnitMismatch:
            continue
        # The tolerance is the golden one, from the published rounding: an answer that rounds more
        # coarsely than the build published (27% for 26.53%) does not pass.
        if abs(v - known.value) <= known.tolerance + 1e-9 * max(1.0, abs(known.value)):
            return True
    if known.unit == "count":
        return any(abs(t.value - known.value) < 0.5 for t in tokens(answer.text))
    return False


def entity_matches(known: str, answer: Answer) -> bool:
    if any(_norm(known) == _norm(s) for s in answer.selection):
        return True
    return bool(answer.selection) is False and _norm(known) in _norm(answer.text.split(":")[0])


def is_refusal(answer: Answer) -> bool:
    return answer.verdict == "refused" or REFUSAL in answer.text


def grade(q: Question, answer: Answer) -> Grade:
    g = Grade(q.id, q.family, False)
    if q.family == "refusal":
        g.checks["refused"] = is_refusal(answer)
        g.checks["no warehouse tool"] = not any(t in WAREHOUSE_TOOLS for t in answer.tools_called)
        g.passed = all(g.checks.values())
        return g
    if is_refusal(answer):
        g.checks["answered"] = False
        g.note = answer.refusal_reason or "refused"
        return g
    if q.family == "definition":
        text = _norm(answer.text)
        for phrase in q.key_phrases:
            g.checks[f"phrase {phrase}"] = _norm(phrase) in text
    elif q.family == "top_k" or (q.family == "multi" and q.ranking):
        got = [s for s in answer.selection]
        known = q.ranking
        if q.family == "multi":
            g.checks["set"] = sorted(map(_norm, got)) == sorted(map(_norm, known))
        else:
            g.checks["order"] = [_norm(x) for x in got[: len(known)]] == [_norm(x) for x in known]
        k = len(known)
        a, b = {_norm(x) for x in got[:k]}, {_norm(x) for x in known}
        g.jaccard = len(a & b) / len(a | b) if a | b else 1.0
    else:
        for i, c in enumerate(q.claims):
            g.checks[f"value {i} ({c.label})"] = value_present(c, answer)
        if q.entity is not None:
            g.checks["entity"] = entity_matches(q.entity, answer)
        if q.direction is not None:
            g.checks["direction"] = answer.direction == q.direction or (answer.direction is None and re.search(rf"\b{q.direction}\b", answer.text) is not None)
    g.passed = bool(g.checks) and all(g.checks.values())
    return g
