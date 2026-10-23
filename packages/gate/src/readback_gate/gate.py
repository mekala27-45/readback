"""The readback gate: every number in an answer is a claim with evidence that re-verifies, or the
answer does not ship.

From the draft answer's text the gate extracts every numeric token with its span. Four rules
exempt a token, each stated here and tested one by one:

  year        a four digit year from 1900 to 2099 standing as a year: not after a currency sign,
              not before a percent sign or a unit word, and not part of a larger number;
  identifier  a code the catalog knows (a CBSA code, a county FIPS, a carrier code with a digit in
              it such as 9E or B6, a quarter such as 2024Q2);
  ordinal     the number of a list item the answer itself numbers, at the start of a line;
  list count  a count equal to the number of items in that list ("these 3 metros").

Every other token must be covered by a claim: the claim's display string at that span, or its
value printed the way the token prints it. Each claim is then read back through the readback tool,
and the answer passes when every token is covered and every readback agrees. The gate is pure code;
the readback it calls re-runs the warehouse, and no model is consulted at any point.
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable, Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

TOKEN = re.compile(
    r"(?<![\w.])(?P<sign>[-+])?(?P<cur>\$)?\s?(?P<num>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)"
    r"(?P<suffix>\s?(?:%|percent\b|pts\b|percentage points\b|million\b|billion\b|thousand\b|[MBk]\b|min\b|minutes\b|x\b))?"
    r"(?![\w])"
)
QUARTER = re.compile(r"\b(?:19|20)\d\dQ[1-4]\b")
LIST_ITEM = re.compile(r"^\s*(\d{1,2})[.)]\s+", re.M)
YEAR_RANGE = (1900, 2099)
UNIT_WORDS = ("%", "percent", "pts", "percentage points", "million", "billion", "thousand", "m", "b", "k", "min", "minutes", "x")

Rule = Literal["year", "identifier", "ordinal", "list count"]


@dataclass(frozen=True)
class Token:
    text: str
    start: int
    end: int
    value: float


@dataclass(frozen=True)
class Exempt:
    token: Token
    rule: Rule


@dataclass
class ClaimCheck:
    index: int
    display: str | None
    value: float
    span: tuple[int, int] | None
    verdict: str = "unchecked"
    reason: str = ""
    evidence: float | None = None
    tolerance: float | None = None


@dataclass
class Report:
    tokens: list[Token]
    exempt: list[Exempt]
    unsupported: list[Token]
    claims: list[ClaimCheck] = field(default_factory=list)
    readback_calls: int = 0

    @property
    def passed(self) -> bool:
        return not self.unsupported and all(c.verdict == "agree" for c in self.claims)

    def failures(self) -> list[str]:
        out = [f"the number {t.text!r} has no claim behind it" for t in self.unsupported]
        out += [f"claim {c.index} ({c.display or c.value}) did not read back: {c.reason}" for c in self.claims if c.verdict != "agree"]
        return out


def _value(m: re.Match[str]) -> float:
    v = float(m.group("num").replace(",", ""))
    return -v if m.group("sign") == "-" else v


def tokens(text: str) -> list[Token]:
    out: list[Token] = []
    quarter_spans = [(q.start(), q.end()) for q in QUARTER.finditer(text)]
    for m in TOKEN.finditer(text):
        if any(a <= m.start("num") < b for a, b in quarter_spans):
            out.append(Token(text[m.start("num") : m.end("num")], m.start("num"), m.end("num"), _value(m)))
            continue
        out.append(Token(text[m.start() : m.end()].strip(), m.start(), m.end(), _value(m)))
    return out


def _numbered_items(text: str) -> list[tuple[int, int, int]]:
    """(number, start, end) of each list item marker the answer numbers itself, if they run 1, 2, 3."""
    items = [(int(m.group(1)), m.start(1), m.end(1)) for m in LIST_ITEM.finditer(text)]
    numbers = [n for n, _, _ in items]
    if numbers and numbers == list(range(1, len(numbers) + 1)):
        return items
    return []


def is_year(token: Token, text: str) -> bool:
    raw = token.text
    if not re.fullmatch(r"\d{4}", raw):
        return False
    if not YEAR_RANGE[0] <= int(raw) <= YEAR_RANGE[1]:
        return False
    after = text[token.end : token.end + 12].lower().lstrip()
    if after.startswith(UNIT_WORDS[:1]) or re.match(r"(percent|pts|million|billion|thousand|min\b|minutes|x\b)", after):
        return False
    before = text[max(0, token.start - 1) : token.start]
    return before != "$"


def check_text(
    text: str,
    claims: Sequence[tuple[str | None, float]],
    identifiers: Iterable[str] = (),
) -> Report:
    """Map every token to an exemption or a claim. Claims are (display, value) in answer order."""
    found = tokens(text)
    ids = {i.lower() for i in identifiers}
    items = _numbered_items(text)
    item_spans = {(s, e) for _, s, e in items}
    count = len(items)
    exempt: list[Exempt] = []
    remaining: list[Token] = []
    for tok in found:
        raw = text[tok.start : tok.end]
        if QUARTER.search(text[max(0, tok.start - 6) : tok.end + 2]) and re.fullmatch(r"\d{4}", tok.text):
            exempt.append(Exempt(tok, "identifier"))
        elif tok.text.lower() in ids or raw.strip().lower() in ids:
            exempt.append(Exempt(tok, "identifier"))
        elif is_year(tok, text):
            exempt.append(Exempt(tok, "year"))
        elif any(tok.start <= s and e <= tok.end for s, e in item_spans):
            exempt.append(Exempt(tok, "ordinal"))
        elif count and re.fullmatch(r"\d+", tok.text) and int(tok.text) == count:
            exempt.append(Exempt(tok, "list count"))
        else:
            remaining.append(tok)
    checks = [ClaimCheck(i, d, v, None) for i, (d, v) in enumerate(claims)]
    unsupported: list[Token] = []
    used: set[int] = set()
    for tok in remaining:
        hit = _match(tok, text, checks, used)
        if hit is None:
            unsupported.append(tok)
        else:
            used.add(hit.index)
            hit.span = (tok.start, tok.end)
    return Report(found, exempt, unsupported, checks)


def _normalize(s: str) -> str:
    return re.sub(r"\s+", "", s.lower()).replace("percent", "%")


def _match(tok: Token, text: str, checks: list[ClaimCheck], used: set[int]) -> ClaimCheck | None:
    window = _normalize(text[tok.start : tok.end + 2])
    for c in checks:
        if c.index in used:
            continue
        if c.display and _normalize(c.display) and window.startswith(_normalize(c.display).lstrip("+")):
            return c
    for c in checks:
        if c.index in used:
            continue
        # A claim without a display string covers a token that prints the same value.
        if c.display is None and abs(c.value - tok.value) <= 1e-9 * max(1.0, abs(tok.value)):
            return c
    return None


Readback = Callable[[int], Awaitable[dict[str, Any]]]


async def verify(report: Report, readback: Readback) -> Report:
    """Read back every claim, whether or not the text used it: a claim must be true to be kept."""
    for c in report.claims:
        out = await readback(c.index)
        report.readback_calls += 1
        c.verdict = str(out.get("verdict", "refused"))
        c.reason = str(out.get("reason", ""))
        c.evidence = out.get("evidence")
        c.tolerance = out.get("tolerance")
    return report
