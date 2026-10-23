"""The deterministic classifier: family, warehouse, measure and the refusal rules.

This is the first stage of the classify node for every provider, and the whole of it for the floor.
The refusal rules run first, in code: a question about another build, about one person, asking for a
forecast or for advice, or naming something no warehouse holds, is refused before any tool is
called. A question the rules cannot place goes to the model when there is one, and is refused by the
floor, which only answers the families it was written for.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from readback_catalog.measures import Measure

Family = Literal["lookup", "comparison", "trend", "top_k", "definition", "multi", "refusal", "unknown"]

OTHER_BUILDS = ("trajectory", "pricepoint", "cityflow", "frontdesk", "groundwork", "readout", "northstar", "rounds",
                "stacks", "docket", "marginal", "lookahead", "shortlist", "legwork")
REFUSALS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("it asks about another build in the series, not doorstep, turnaround or ledger",
     re.compile(r"\b(" + "|".join(OTHER_BUILDS) + r")\b", re.I)),
    ("it asks about one person, customer, account or loan",
     re.compile(r"\b(customer|account|borrower|applicant|loan)\s+(?:id\s+)?[A-Z]{0,3}\d{3,}\b|\bloan officer\b|\bhome address\b|"
                r"\bwho (?:is|was) the (?:borrower|customer)\b|\bnamed?\b.*\b(?:customer|borrower)\b|\bC\d{5,}\b", re.I)),
    ("it asks for a forecast, and the warehouses hold only what was published",
     re.compile(r"\bwill\b|\bnext (?:year|month|week|quarter|friday|monday|summer|winter)\b|\bforecast(?:s|ed)?\b(?!\s+error)|"
                r"\bpredict|\btomorrow\b|\bin 20(?:2[7-9]|[3-9]\d)\b", re.I)),
    ("it asks for advice, which readback does not give",
     re.compile(r"\bshould i\b|\bgood time to\b|\brecommend|\bvote\b|\bbook\b.*\bflight|\bwhich flight should\b|\bworth it\b", re.I)),
    ("it is not a question about the three warehouses",
     re.compile(r"\bignore (?:the|all|your)\b|\btell me a joke\b|\bsystem prompt\b|\bpretend\b", re.I)),
)
FAMILY_RULES: tuple[tuple[Family, re.Pattern[str]], ...] = (
    ("multi", re.compile(r"publishes more tables|has more rows|appear in both|\bin total\b|between them", re.I)),
    ("definition", re.compile(r"\bmean by\b|\bdefine[sd]?\b|\bdefinition of\b", re.I)),
    ("trend", re.compile(r"rise or fall|go up or down|increase or decrease|rose or fell", re.I)),
    ("top_k", re.compile(r"\bwhich (\d+)\b.*\b(highest|lowest)\b|\b(top|bottom) (\d+)\b", re.I)),
    ("comparison", re.compile(r"\bhigher\b.*\bor\b|\blower\b.*\bor\b|\bwhich (?:carrier|airport|group|rule|metro)? ?had the (?:higher|lower)\b", re.I)),
    ("lookup", re.compile(r"^\s*(?:in [^,]+,\s*)?what (?:was|is|were)\b", re.I)),
)
WAREHOUSE_HINTS: dict[str, re.Pattern[str]] = {
    "ledger": re.compile(r"\bledger\b|\bharborline\b|\bbank\b|\bhmda\b|\baml\b|\bquarters?\b|\b20\d\dQ[1-4]\b", re.I),
    "turnaround": re.compile(r"\bturnaround\b|\bcarriers?\b|\bairlines?\b|\bairports?\b|\bflights?\b|\bon time\b", re.I),
    "doorstep": re.compile(r"\bdoorstep\b|\bmetros?\b|\bhouseholds\b|\bhome\b|\brent(?:ers?)?\b|\bmortgage\b|\bpermits?\b", re.I),
}


@dataclass
class Classification:
    family: Family
    warehouses: list[str] = field(default_factory=list)
    measure: Measure | None = None
    refusal: str | None = None
    rule: str = ""


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().replace("-", " ")).strip()


def refusal_reason(question: str) -> str | None:
    for reason, pattern in REFUSALS:
        if pattern.search(question):
            return reason
    return None


def family_of(question: str) -> Family:
    for family, pattern in FAMILY_RULES:
        if pattern.search(question):
            return family
    return "unknown"


def warehouse_hints(question: str) -> list[str]:
    return [w for w, p in WAREHOUSE_HINTS.items() if p.search(question)]


def match_measure(question: str, measures: list[Measure], airport_named: bool) -> Measure | None:
    """The measure whose phrase the question uses, longest phrase first, with the entity deciding a tie."""
    q = normalize(question)
    hints = warehouse_hints(question)
    scored: list[tuple[int, int, str, Measure]] = []
    for m in measures:
        best = max((len(p) for p in m.phrases if normalize(p) in q), default=0)
        if not best:
            continue
        bonus = 0
        if m.warehouse in hints:
            bonus += 2
        if m.entity == "airport":
            bonus += 3 if airport_named else -5
        if m.entity == "carrier" and airport_named and "carrier" not in q:
            bonus -= 3
        if m.entity == "nation" and not re.search(r"\bnational\b|\bacross all\b|\bthirty year\b|\b30 year\b", q):
            bonus -= 4
        if m.entity == "bank" and "ledger" not in hints:
            bonus -= 4
        scored.append((best + bonus, best, m.id, m))
    if not scored:
        return None
    scored.sort(key=lambda s: (-s[0], -s[1], s[2]))
    return scored[0][3]


def classify(question: str, measures: list[Measure], *, airport_named: bool = False) -> Classification:
    reason = refusal_reason(question)
    if reason:
        return Classification("refusal", refusal=reason, rule="refusal rule")
    family = family_of(question)
    if family == "definition":
        return Classification(family, warehouse_hints(question)[:1], rule="definition cue")
    if family == "multi":
        named = [w for w in ("doorstep", "turnaround", "ledger") if re.search(rf"\b{w}\b", question, re.I)]
        return Classification(family, named, rule="multi cue")
    measure = match_measure(question, measures, airport_named)
    if measure is None:
        return Classification("unknown", warehouse_hints(question), rule="no measure phrase")
    if family == "unknown":
        family = "lookup"
    return Classification(family, [measure.warehouse], measure, rule=f"measure {measure.id}")
