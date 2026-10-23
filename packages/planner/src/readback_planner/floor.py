"""The floor: answers the golden families with no model anywhere.

A grammar over the families (the classifier), entity dictionaries built from the catalog, and SQL
templates per measure (catalog/measures.yaml). It compiles a plan, calls the same MCP tools over the
same client as any model, and produces the same Draft with the same evidence, which the same gate
reads back. It is graded like a model, and it is what the live site runs when no key is present or
every budget is spent.
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from readback_catalog.measures import Measure, load, period_ranking_sql, quote, ranking_sql, value_sql
from readback_core import paths
from readback_core.answer import Choice, Draft, DraftClaim
from readback_core.formats import format_value
from readback_core.statements import REFUSAL
from readback_core.units import FRACTIONAL

from readback_planner.classify import Classification, classify

CallTool = Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]]
FULL_QUARTERS = [f"{y}Q{q}" for y in (2023, 2024, 2025, 2026) for q in (1, 2, 3, 4) if "2023Q4" <= f"{y}Q{q}" <= "2026Q2"]
YEAR = re.compile(r"\b(19\d\d|20\d\d)\b(?!Q)")
QUARTER = re.compile(r"\b(20\d\dQ[1-4])\b")
TOP_K = re.compile(r"\bwhich (\d+)\b|\b(?:top|bottom) (\d+)\b", re.I)
NUMBER = re.compile(r"[-+]?\$?\d[\d,]*(?:\.\d+)?")


class FloorCannot(ValueError):
    """The floor's grammar does not cover the question; the reason is the refusal it gives."""


@dataclass
class Step:
    tool: str
    args: dict[str, Any]


@dataclass
class FloorResult:
    draft: Draft
    classification: Classification
    plan: list[Step] = field(default_factory=list)
    needs_choice: Choice | None = None


@dataclass(frozen=True)
class Mention:
    kind: str
    text: str
    value: str
    start: int


class Dictionaries:
    """Entity names from the catalog, the way a person writes them, mapped to the warehouse spelling."""

    def __init__(self, metros: list[tuple[str, str]], entities: dict[str, Any]) -> None:
        self.names: list[tuple[str, str, str]] = []  # (kind, written form, warehouse value)
        firsts: dict[str, list[str]] = {}
        for title, kind in metros:
            self.names.append(("metro", title, title))
            first = re.split(r"[-,]", title)[0].strip()
            firsts.setdefault(first, []).append(title if kind == "metropolitan" else "")
        for first, titles in firsts.items():
            metro_titles = [t for t in titles if t]
            all_titles = [t for t, _ in metros if re.split(r"[-,]", t)[0].strip() == first]
            if len(all_titles) == 1:
                self.names.append(("metro", first, all_titles[0]))
            elif len(metro_titles) == 1:
                self.names.append(("metro", first, metro_titles[0]))
        for code, aliases in entities.get("carriers", {}).items():
            for a in aliases:
                self.names.append(("carrier", str(a), str(code)))
        for code, aliases in entities.get("airports", {}).items():
            self.names.append(("airport", str(code), str(code)))
        for group in entities.get("applicant_groups", {}):
            self.names.append(("applicant_group", str(group), str(group)))
        for rule, aliases in entities.get("aml_rules", {}).items():
            self.names.append(("aml_rule", str(rule).replace("_", " "), str(rule)))
            for a in aliases:
                self.names.append(("aml_rule", str(a), str(rule)))
        # Longest written form first, so "Los Angeles-Long Beach-Anaheim, CA" wins over "Los Angeles".
        self.names.sort(key=lambda n: (-len(n[1]), n[0], n[1]))

    def find(self, question: str, kinds: set[str]) -> list[Mention]:
        taken: list[tuple[int, int]] = []
        found: list[Mention] = []
        for kind, written, value in self.names:
            if kind not in kinds:
                continue
            flags = 0 if kind == "airport" else re.I
            for m in re.finditer(rf"(?<![\w-]){re.escape(written)}(?![\w-])", question, flags):
                span = (m.start(), m.end())
                if any(a < span[1] and span[0] < b for a, b in taken):
                    continue
                taken.append(span)
                found.append(Mention(kind, written, value, m.start()))
        found.sort(key=lambda x: x.start)
        return found


def _display(value: float, m: Measure) -> tuple[float, str, str]:
    """The value as the text shows it, its unit, and the display string."""
    shown = format_value(value, m.fmt)
    number = float(NUMBER.search(shown).group(0).replace("$", "").replace(",", ""))  # type: ignore[union-attr]
    unit = "percent" if m.unit in FRACTIONAL and "%" in shown else m.unit
    return number, unit, shown


def _name(m: Measure, value: str, written: dict[str, str]) -> str:
    return written.get(value, value)


class Floor:
    _shared: Dictionaries | None = None

    def __init__(self, call: CallTool, root: Path | None = None) -> None:
        self.call = call
        self.root = root or paths.root()
        self.measures = load(self.root / "catalog" / "measures.yaml")
        self.entities = yaml.safe_load((self.root / "catalog" / "entities.yaml").read_text(encoding="utf-8"))
        self._dict: Dictionaries | None = Floor._shared
        self.plan: list[Step] = []

    async def tool(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        self.plan.append(Step(name, args))
        return await self.call(name, args)

    async def dictionaries(self) -> Dictionaries:
        if self._dict is None:
            out = await self.tool("run_sql", {"warehouse": "doorstep", "sql": "select distinct cbsa_title, kind from mart_metro_year order by cbsa_title", "limit": 500})
            rows = [(r[0], r[1]) for r in out["rows"]]
            if out["row_count"] > len(rows):
                more = await self.tool("run_sql", {"warehouse": "doorstep", "sql": "select distinct cbsa_title, kind from mart_metro_year where kind = 'metropolitan' order by cbsa_title", "limit": 500})
                rows = sorted({*rows, *[(r[0], r[1]) for r in more["rows"]]})
            self._dict = Dictionaries(rows, self.entities)
            Floor._shared = self._dict
            self.plan = []  # building the dictionaries once per process is not part of the question's plan
        return self._dict

    async def answer(self, question: str, choice: str | None = None) -> FloorResult:
        self.plan = []
        d = await self.dictionaries()
        airports = d.find(question, {"airport"})
        c = classify(question, self.measures, airport_named=bool(airports))
        if c.family == "refusal":
            return FloorResult(Draft(text=f"{REFUSAL} This question was refused because {c.refusal}.", refused=True, refusal_reason=c.refusal), c, self.plan)
        try:
            if c.family == "definition":
                draft = await self.definition(question, c)
            elif c.family == "multi":
                draft = await self.multi(question)
            elif c.measure is None:
                raise FloorCannot("it names no measure the warehouses publish")
            else:
                mentions = d.find(question, {c.measure.entity})
                if c.measure.entity in {"metro", "carrier", "airport"} and not mentions and c.family != "top_k":
                    ambiguous = self._ambiguous(question, c.measure.entity)
                    if ambiguous and choice is None:
                        return FloorResult(Draft(text="", refused=False), c, self.plan, needs_choice=ambiguous)
                    if ambiguous and choice:
                        mentions = [Mention(c.measure.entity, choice, choice, question.find(ambiguous.name))]
                    else:
                        raise FloorCannot(f"it names a {c.measure.entity} that is not in the {c.measure.warehouse} warehouse")
                draft = await getattr(self, c.family)(question, c.measure, mentions)
        except FloorCannot as err:
            return FloorResult(Draft(text=f"{REFUSAL} This question was refused because {err}.", refused=True, refusal_reason=str(err)), c, self.plan)
        return FloorResult(draft, c, self.plan)

    def _ambiguous(self, question: str, kind: str) -> Choice | None:
        for word, spec in self.entities.get("ambiguous", {}).items():
            if spec["kind"] == kind and re.search(rf"\b{re.escape(word)}\b", question, re.I) and len(spec["candidates"]) > 1:
                return Choice(kind=kind, name=word, candidates=list(spec["candidates"]))
        return None

    # SQL and claims

    async def value(self, m: Measure, entity: str | None, time: str | int | None) -> tuple[float, str]:
        out = await self.tool("run_sql", {"warehouse": m.warehouse, "sql": value_sql(m, entity, time)})
        if not out["rows"] or out["rows"][0][0] is None:
            raise FloorCannot(f"the warehouse has no {m.phrases[0]} for {entity or 'that'} in {time}")
        return float(out["rows"][0][0]), str(out["result_id"])

    def claim(self, m: Measure, value: float, rid: str, row: int = 0, column: str = "value") -> DraftClaim:
        shown_value, unit, shown = _display(value, m)
        return DraftClaim(value=shown_value, unit=unit, display=shown, warehouse=m.warehouse,  # type: ignore[arg-type]
                          result_id=rid, column=column, row=row, evidence_unit=m.unit)

    def times(self, question: str, m: Measure) -> list[str | int]:
        if m.time == "year":
            return [int(y) for y in YEAR.findall(question)]
        if m.time == "quarter":
            return list(QUARTER.findall(question))
        return []

    @staticmethod
    def where(m: Measure, name: str) -> str:
        return {"metro": f"in {name}", "carrier": f"for {name}", "airport": f"at {name}",
                "applicant_group": f"for {name} applicants", "aml_rule": f"for the {name.replace('_', ' ')} rule"}.get(m.entity, "")

    def written(self, mentions: list[Mention]) -> dict[str, str]:
        return {x.value: x.text for x in mentions}

    async def lookup(self, question: str, m: Measure, mentions: list[Mention]) -> Draft:
        times = self.times(question, m)
        entity = mentions[0].value if mentions and m.entity_column else None
        if m.entity_column and entity is None:
            raise FloorCannot(f"it names no {m.entity} the {m.warehouse} warehouse has")
        if m.time != "none" and not times:
            raise FloorCannot(f"it gives no {m.time} to read the {m.phrases[0]} at")
        t = times[0] if times else None
        v, rid = await self.value(m, entity, t)
        c = self.claim(m, v, rid)
        subject = self.where(m, mentions[0].text) if entity else ("at Harborline Bank" if m.entity == "bank" else "")
        when = f" in {t}" if t is not None else ""
        text = f"The {m.phrases[0]} {subject}{when} was {c.display}.".replace("  ", " ").replace(" .", ".")
        return Draft(text=text, claims=[c], warehouses=[m.warehouse], selection=[entity] if entity else [])

    async def comparison(self, question: str, m: Measure, mentions: list[Mention]) -> Draft:
        times = self.times(question, m)
        if m.entity in {"nation", "bank"}:
            if len(times) < 2:
                raise FloorCannot("it does not give two times to compare")
            a, b = times[0], times[1]
            va, ra = await self.value(m, None, a)
            vb, rb = await self.value(m, None, b)
            ca, cb = self.claim(m, va, ra), self.claim(m, vb, rb)
            win, lose, cw, cl = (a, b, ca, cb) if va > vb else (b, a, cb, ca)
            where = " at Harborline Bank" if m.entity == "bank" else ""
            text = f"The {m.phrases[0]}{where} was higher in {win}: {cw.display} against {cl.display} in {lose}."
            claims = [cw, cl]
            return Draft(text=text, claims=claims, warehouses=[m.warehouse], selection=[str(win)])
        if len(mentions) < 2:
            raise FloorCannot(f"it does not name two {m.entity}s to compare")
        t = times[0] if times else None
        if m.time != "none" and t is None:
            raise FloorCannot(f"it gives no {m.time} for the comparison")
        x, y = mentions[0], mentions[1]
        vx, rx = await self.value(m, x.value, t)
        vy, ry = await self.value(m, y.value, t)
        cx, cy = self.claim(m, vx, rx), self.claim(m, vy, ry)
        (w, cw), (l_, cl) = ((x, cx), (y, cy)) if vx > vy else ((y, cy), (x, cx))
        when = f" in {t}" if t is not None else ""
        text = f"{w.text} had the higher {m.phrases[0]}{when}: {cw.display}, against {cl.display} for {l_.text}."
        return Draft(text=text, claims=[cw, cl], warehouses=[m.warehouse], selection=[w.value])

    async def trend(self, question: str, m: Measure, mentions: list[Mention]) -> Draft:
        times = self.times(question, m)
        if len(times) < 2:
            raise FloorCannot("it does not give a start and an end")
        entity = mentions[0].value if mentions and m.entity_column else None
        if m.entity_column and entity is None:
            raise FloorCannot(f"it names no {m.entity}")
        a, b = times[0], times[1]
        va, ra = await self.value(m, entity, a)
        vb, rb = await self.value(m, entity, b)
        ca, cb = self.claim(m, va, ra), self.claim(m, vb, rb)
        direction = "rose" if cb.value > ca.value else ("fell" if cb.value < ca.value else "unchanged")
        if m.entity == "bank":
            subject = "Harborline Bank's " + m.phrases[0]
        elif entity:
            subject = f"The {m.phrases[0]} {self.where(m, mentions[0].text)}"
        else:
            subject = f"The {m.phrases[0]}"
        text = f"{subject} {direction} from {ca.display} in {a} to {cb.display} in {b}."
        return Draft(text=text[0].upper() + text[1:], claims=[ca, cb], warehouses=[m.warehouse], direction=direction)  # type: ignore[arg-type]

    async def top_k(self, question: str, m: Measure, mentions: list[Mention]) -> Draft:
        k_match = TOP_K.search(question)
        k = int(next(g for g in k_match.groups() if g)) if k_match else 3
        highest = bool(re.search(r"\bhighest\b|\btop\b", question, re.I))
        times = self.times(question, m)
        t = times[0] if times else None
        if m.entity == "bank":
            sql = period_ranking_sql(m, k, highest, FULL_QUARTERS)
        elif m.entity == "metro":
            floor = "households >= 1000000" if re.search(r"at least a million households", question, re.I) else None
            sql = ranking_sql(m, t, k, highest, floor=floor)
        elif m.entity == "carrier":
            having = "sum(flown) >= 500000" if re.search(r"half a million flights", question, re.I) else None
            sql = ranking_sql(m, t, k, highest, having=having)
        elif m.entity == "airport":
            named = [x.value for x in mentions] or [str(a) for a in self.entities.get("airports", {})]
            sql = ranking_sql(m, t, k, highest, floor="airport in (" + ", ".join(quote(a) for a in named) + ")")
        else:
            sql = ranking_sql(m, None, k, highest)
        out = await self.tool("run_sql", {"warehouse": m.warehouse, "sql": sql})
        rows = out["rows"]
        if not rows:
            raise FloorCannot("the ranking returned no rows")
        rid = str(out["result_id"])
        claims = [self.claim(m, float(r[1]), rid, row=i) for i, r in enumerate(rows)]
        names = [str(r[0]) for r in rows]
        carrier_names = {code: aliases[0] for code, aliases in self.entities.get("carriers", {}).items()}
        label = (lambda v: f"{carrier_names.get(v, v)} ({v})") if m.entity == "carrier" else (lambda v: v.replace("_", " "))
        word = "highest" if highest else "lowest"
        when = f" in {t}" if t is not None else ""
        lines = [f"{i + 1}. {label(n)}: {c.display}" for i, (n, c) in enumerate(zip(names, claims, strict=True))]
        text = f"The {len(rows)} with the {word} {m.phrases[0]}{when}:\n" + "\n".join(lines)
        return Draft(text=text, claims=claims, warehouses=[m.warehouse], selection=names)

    async def definition(self, question: str, c: Classification) -> Draft:
        m = re.search(r"(?:mean by|define|definition of)\s+(.+?)\??$", question, re.I)
        term = (m.group(1) if m else question).strip()
        warehouse = c.warehouses[0] if c.warehouses else None
        args: dict[str, Any] = {"query": term, "k": 5, "kind": "definition"}
        if warehouse:
            args["warehouse"] = warehouse
        out = await self.tool("search_catalog", args)
        hit = next((h for h in out["hits"] if h["kind"] == "definition"), None)
        if hit is None:
            raise FloorCannot(f"the definitions documents have no entry for {term}")
        doc_id = f"{hit['warehouse']}.definition.{re.sub(r'[^a-z0-9]+', '_', hit['name'].split(' (')[0].lower()).strip('_')}"
        body = hit["definition"]
        text = f"In {hit['warehouse']}'s definitions document: {body}"
        from readback_gate.gate import check_text

        report = check_text(text, [])
        claims = []
        for tok in report.unsupported:
            number = float(NUMBER.search(tok.text).group(0).replace("$", "").replace(",", ""))  # type: ignore[union-attr]
            unit = "percent" if "%" in tok.text else "none"
            claims.append(DraftClaim(value=number, unit=unit, display=tok.text, warehouse=hit["warehouse"], definition_id=doc_id))
        return Draft(text=text, claims=claims, warehouses=[hit["warehouse"]])

    async def multi(self, question: str) -> Draft:
        named = [w for w in ("doorstep", "turnaround", "ledger") if re.search(rf"\b{w}\b", question, re.I)]
        q = question.lower()
        if "publishes more tables" in q and len(named) == 2:
            info = {w["name"]: w for w in (await self.tool("warehouses", {}))["warehouses"]}
            a, b = named
            ca = DraftClaim(value=info[a]["tables"], unit="count", display=f"{info[a]['tables']:,}", catalog_key=f"{a}.tables")
            cb = DraftClaim(value=info[b]["tables"], unit="count", display=f"{info[b]['tables']:,}", catalog_key=f"{b}.tables")
            win = a if info[a]["tables"] > info[b]["tables"] else b
            text = f"{win} publishes more tables: {a} has {ca.display} and {b} has {cb.display}."
            return Draft(text=text, claims=[ca, cb], warehouses=[a, b], selection=[win])
        if "tables" in q and "in total" in q:
            info = (await self.tool("warehouses", {}))["warehouses"]
            total = sum(w["tables"] for w in info)
            parts = [DraftClaim(value=w["tables"], unit="count", display=f"{w['tables']:,}", catalog_key=f"{w['name']}.tables") for w in info]
            whole = DraftClaim(value=total, unit="count", display=f"{total:,}", catalog_key="+".join(w["name"] for w in info) + ".tables")
            text = f"They publish {whole.display} tables in total: " + ", ".join(f"{w['name']} {p.display}" for w, p in zip(info, parts, strict=True)) + "."
            return Draft(text=text, claims=[whole, *parts], warehouses=[w["name"] for w in info])
        rows = re.search(r"more rows, (\w+)'s (\w+) or (\w+)'s (\w+)", question)
        if rows:
            wa, ta, wb, tb = rows.groups()
            oa = await self.tool("run_sql", {"warehouse": wa, "sql": f"select count(*) as n from {ta}"})
            ob = await self.tool("run_sql", {"warehouse": wb, "sql": f"select count(*) as n from {tb}"})
            na, nb = int(oa["rows"][0][0]), int(ob["rows"][0][0])
            ca = DraftClaim(value=na, unit="count", display=f"{na:,}", warehouse=wa, result_id=oa["result_id"], column="n")  # type: ignore[arg-type]
            cb = DraftClaim(value=nb, unit="count", display=f"{nb:,}", warehouse=wb, result_id=ob["result_id"], column="n")  # type: ignore[arg-type]
            win = f"{wa}.{ta}" if na > nb else f"{wb}.{tb}"
            text = f"{win} has more rows: {wa}.{ta} has {ca.display} and {wb}.{tb} has {cb.display}."
            return Draft(text=text, claims=[ca, cb], warehouses=[wa, wb], selection=[win])
        if "appear in both" in q and len(named) == 2:
            years = []
            for w in named:
                sql = {
                    "doorstep": "select distinct year from ch1_national_series order by 1" if "national series" in q else "select distinct year from mart_metro_year where median_income is not null order by 1",
                    "turnaround": "select distinct year from mart_carrier_month order by 1",
                    "ledger": "select distinct cast(period as integer) as year from metrics_bank_year order by 1",
                }[w]
                out = await self.tool("run_sql", {"warehouse": w, "sql": sql})
                years.append({int(r[0]) for r in out["rows"]})
            both = sorted(years[0] & years[1])
            listed = ", ".join(str(y) for y in both[:-1]) + (f" and {both[-1]}" if len(both) > 1 else (str(both[0]) if both else "none"))
            text = f"The years in both are {listed}."
            return Draft(text=text, warehouses=named, selection=[str(y) for y in both])
        if ("metrics" in q and "between them" in q) or ("manifest" in q and "in total" in q):
            fact, noun = ("metrics", "metrics") if "metrics" in q else ("manifest_values", "values")
            pair = named or (["doorstep", "turnaround"] if fact == "metrics" else ["doorstep", "turnaround", "ledger"])
            info = {w["name"]: w for w in (await self.tool("warehouses", {}))["warehouses"]}
            claims = [DraftClaim(value=info[w][fact], unit="count", display=f"{info[w][fact]:,}", catalog_key=f"{w}.{fact}") for w in pair]
            total = sum(info[w][fact] for w in pair)
            whole = DraftClaim(value=total, unit="count", display=f"{total:,}", catalog_key="+".join(pair) + f".{fact}")
            parts = ", ".join(f"{w} {c.display}" for w, c in zip(pair, claims, strict=True))
            text = f"Between them they publish {whole.display} {noun}: {parts}."
            return Draft(text=text, claims=[whole, *claims], warehouses=pair)
        raise FloorCannot("it needs two warehouses in a way the floor was not written for")
