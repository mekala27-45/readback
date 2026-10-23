"""The seven tools, as plain functions over the server state, so they test without a transport.

server.py wraps each in the MCP decorator; the agent's tests and the eval call them through the
in memory client, never directly, so the protocol path is the one that is measured.
"""

from __future__ import annotations

import difflib
import fnmatch
import re
from typing import Any

from readback_core.formats import format_value
from readback_core.units import spec
from readback_gate.compare import compare
from readback_warehouse.guard import Refused, guard
from readback_warehouse.run import TimedOut, execute

from readback_mcp_server.schemas import (
    Claim,
    ColumnOut,
    DescribeOut,
    LookupCandidate,
    LookupOut,
    PublishedOut,
    PublishedValue,
    ReadbackOut,
    RunSqlOut,
    SearchHit,
    SearchOut,
    SqlColumn,
    WarehouseInfo,
    WarehousesOut,
)
from readback_mcp_server.state import BadHandle, State

SEARCH_CEILING = 20
PUBLISHED_CEILING = 50
EXAMPLES = 5


class ToolRefusal(ValueError):
    """A tool refused its arguments; the message says why and what to try instead."""


def _check_warehouse(state: State, warehouse: str) -> None:
    if warehouse not in state.catalogs:
        raise ToolRefusal(f"there is no warehouse {warehouse!r}; the three are doorstep, turnaround and ledger")


def warehouses(state: State) -> WarehousesOut:
    out = []
    for name, c in state.catalogs.items():
        out.append(
            WarehouseInfo(
                name=name,  # type: ignore[arg-type]
                repository=c.repository,
                tag=c.tag,
                commit=c.commit,
                tables=len(c.tables),
                rows=sum(t.rows for t in c.tables),
                metrics=len(c.metrics),
                manifest_values=len(state.manifest[name]),
                as_of=c.as_of,
                covers=c.covers,
            )
        )
    return WarehousesOut(warehouses=out)


def describe(state: State, warehouse: str, table: str) -> DescribeOut:
    _check_warehouse(state, warehouse)
    entry = state.catalogs[warehouse].table(table)
    if entry is None:
        near = difflib.get_close_matches(table, state.tables(warehouse), n=3, cutoff=0.0)
        raise ToolRefusal(f"{warehouse} has no table {table!r}; the nearest names are {', '.join(near)}")
    order = [g for g in entry.grain if entry.column(g) is not None] or [entry.columns[0].name]
    order_sql = ", ".join(f'"{c}"' for c in order)
    cols, rows = state.warehouse.query(f'select * from {warehouse}."{entry.name}" order by {order_sql} limit {EXAMPLES}')
    from readback_warehouse.run import plain

    examples = [{c: plain(v) for c, v in zip(cols, r, strict=True)} for r in rows]
    columns = [
        ColumnOut(
            name=c.name,
            type=c.type,
            role=c.role,
            unit=c.unit,
            definition=c.definition,
            cited=f"{c.citation.file}:{c.citation.line}" if c.citation and c.citation.line else None,
        )
        for c in entry.columns
    ]
    return DescribeOut(
        warehouse=warehouse,  # type: ignore[arg-type]
        table=entry.name,
        grain=entry.grain,
        rows=entry.rows,
        source_step=entry.source_step,
        columns=columns,
        manifest_keys=state.figure_tables[warehouse].get(entry.name, []),
        examples=examples,
    )


def search_catalog(state: State, query: str, k: int = 8, warehouse: str | None = None, kind: str | None = None) -> SearchOut:
    if warehouse is not None:
        _check_warehouse(state, warehouse)
    k = max(1, min(int(k), SEARCH_CEILING))
    expanded = state.synonyms.expand(query)
    hits = state.index.search(expanded, k, warehouse=warehouse, kinds=(kind,) if kind else ())
    return SearchOut(
        query=query,
        expanded=expanded,
        hits=[
            SearchHit(
                kind=h.doc.kind,  # type: ignore[arg-type]
                warehouse=h.doc.warehouse,  # type: ignore[arg-type]
                name=h.doc.name,
                unit=h.doc.unit,
                definition=_one_definition(h.doc.kind, h.doc.definition),
                score=h.score,
            )
            for h in hits
        ],
    )


def _one_definition(kind: str, text: str | None) -> str | None:
    """One definition sentence for a column or a table; a definitions entry is kept whole, up to 600 characters."""
    if not text:
        return None
    if kind == "definition":
        return text[:600]
    return text.split(". ")[0][:240]


def catalog_fact(state: State, key: str) -> float:
    """A count the catalog knows: tables, rows, metrics or manifest values, summed over warehouses joined by +."""
    parts = key.split(".")
    if len(parts) not in (2, 3):
        raise ToolRefusal(f"{key!r} is not a catalog key")
    names = parts[0].split("+")
    total = 0
    for name in names:
        _check_warehouse(state, name)
        c = state.catalogs[name]
        if len(parts) == 3:
            table = c.table(parts[1])
            if table is None or parts[2] != "rows":
                raise ToolRefusal(f"{key!r} names no table row count")
            total += table.rows
        elif parts[1] == "tables":
            total += len(c.tables)
        elif parts[1] == "rows":
            total += sum(t.rows for t in c.tables)
        elif parts[1] == "metrics":
            total += len(c.metrics)
        elif parts[1] == "manifest_values":
            total += len(state.manifest[name])
        else:
            raise ToolRefusal(f"the catalog knows tables, rows, metrics and manifest_values, not {parts[1]!r}")
    return float(total)


def run_sql(state: State, warehouse: str, sql: str, limit: int | None, chain: str) -> RunSqlOut:
    _check_warehouse(state, warehouse)
    try:
        g = guard(sql, warehouse, state.tables(warehouse), limit)
    except Refused as err:
        raise ToolRefusal(str(err)) from err
    try:
        r = execute(state.warehouse, g)
    except TimedOut as err:
        raise ToolRefusal(str(err)) from err
    except Exception as err:  # a binder or type error in a well formed SELECT
        raise ToolRefusal(f"the statement failed in the warehouse: {str(err).splitlines()[0][:200]}") from err
    columns = [
        SqlColumn(name=c, type=t, unit=state.column_unit(warehouse, g.tables, c))
        for c, t in zip(r.columns, r.types, strict=True)
    ]
    return RunSqlOut(
        warehouse=warehouse,  # type: ignore[arg-type]
        sql=g.sql,
        columns=columns,
        rows=r.rows,
        row_count=r.row_count,
        limit=g.limit,
        elapsed_ms=r.elapsed_ms,
        digest=r.digest,
        result_id=state.mint(warehouse, g.sql, r.digest, chain),
    )


def published(state: State, warehouse: str, key_or_pattern: str) -> PublishedOut:
    _check_warehouse(state, warehouse)
    entries = state.manifest[warehouse]
    pattern = key_or_pattern.strip()
    if any(ch in pattern for ch in "*?["):
        keys = sorted(k for k in entries if fnmatch.fnmatchcase(k, pattern))
    else:
        keys = [pattern] if pattern in entries else []
    if not keys:
        near = difflib.get_close_matches(pattern, sorted(entries), n=3, cutoff=0.0)
        raise ToolRefusal(f"{warehouse}'s manifest has no key matching {pattern!r}; the nearest keys are {', '.join(near)}")
    matched = len(keys)
    values = []
    for key in keys[:PUBLISHED_CEILING]:
        e = entries[key]
        raw: Any = e.value if e.value is not None else e.text
        values.append(
            PublishedValue(
                key=key,
                value=e.value,
                text=e.text,
                display=format_value(raw, e.fmt),
                unit=e.unit,
                rounding=e.step,
                low=e.low,
                high=e.high,
                population=e.population,
                table=None,
                sql=None,
            )
        )
    return PublishedOut(warehouse=warehouse, pattern=pattern, matches=matched, values=values)  # type: ignore[arg-type]


def _refused(claim: Claim, reason: str) -> ReadbackOut:
    return ReadbackOut(
        verdict="refused",
        claim=claim.value,
        claim_unit=claim.unit,
        evidence=None,
        evidence_unit=None,
        unit_source="none",
        difference=None,
        tolerance=None,
        reason=reason,
        evidence_ref="",
    )


def _readback_definition(state: State, claim: Claim) -> ReadbackOut:
    """A number the build's own definitions document prints: agree when the document prints it."""
    from readback_gate.gate import tokens

    doc = next((d for d in state.index.docs if d.id == claim.definition_id and d.kind == "definition"), None)
    if doc is None:
        return _refused(claim, f"there is no definition {claim.definition_id!r}")
    printed = [t.value for t in tokens(doc.definition or "")]
    match = [v for v in printed if abs(v - claim.value) <= 1e-9 * max(1.0, abs(v))]
    verdict = "agree" if match else "disagree"
    reason = (f"{doc.name} prints {claim.display or claim.value}" if match
              else f"{doc.name} does not print {claim.display or claim.value}")
    return ReadbackOut(verdict=verdict, claim=claim.value, claim_unit=claim.unit, evidence=match[0] if match else None,
                       evidence_unit=claim.unit, unit_source="catalog", difference=0.0 if match else None,
                       tolerance=0.0, reason=reason, evidence_ref=doc.id)


def _cell(columns: list[str], rows: list[list[Any]], column: str | None, row: int) -> tuple[str, Any]:
    if not rows:
        raise ToolRefusal("the result has no rows to read a value from")
    if row >= len(rows):
        raise ToolRefusal(f"the result has {len(rows)} rows; row {row} does not exist")
    if column is None:
        numeric = [i for i, v in enumerate(rows[row]) if isinstance(v, (int, float)) and not isinstance(v, bool)]
        if len(numeric) != 1:
            raise ToolRefusal("name the column: the row has more than one number in it")
        return columns[numeric[0]], rows[row][numeric[0]]
    if column not in columns:
        raise ToolRefusal(f"the result has no column {column!r}; it has {', '.join(columns)}")
    i = columns.index(column)
    return column, rows[row][i]


def readback(state: State, claim: Claim, chain: str) -> ReadbackOut:
    """Re-run or look up the evidence for one claim and compare it in the claim's unit."""
    sources = [s for s in (claim.result_id, claim.sql, claim.manifest_key, claim.catalog_key, claim.definition_id) if s]
    if len(sources) != 1:
        return _refused(claim, "a claim needs exactly one of result_id, sql, manifest_key, catalog_key or definition_id")
    try:
        if claim.definition_id:
            return _readback_definition(state, claim)
        if claim.catalog_key:
            fact = catalog_fact(state, claim.catalog_key)
            c = compare(claim.value, claim.unit, fact, "count", published_step=1.0)
            return ReadbackOut(verdict=c.verdict, claim=claim.value, claim_unit=claim.unit, evidence=c.evidence,
                               evidence_unit="count", unit_source="catalog", difference=c.difference,
                               tolerance=c.tolerance, reason=c.reason, evidence_ref=f"catalog:{claim.catalog_key}")
        if claim.manifest_key:
            if claim.warehouse is None:
                return _refused(claim, "a manifest key needs its warehouse")
            entry = state.manifest[claim.warehouse].get(claim.manifest_key)
            if entry is None:
                return _refused(claim, f"{claim.warehouse}'s manifest has no key {claim.manifest_key!r}")
            if entry.value is None:
                return _refused(claim, f"{claim.manifest_key} is text, not a number")
            c = compare(claim.value, claim.unit, entry.value, entry.unit, published_step=entry.step)
            return ReadbackOut(
                verdict=c.verdict,
                claim=claim.value,
                claim_unit=claim.unit,
                evidence=c.evidence,
                evidence_unit=entry.unit,
                unit_source="manifest",
                difference=c.difference,
                tolerance=c.tolerance,
                reason=c.reason,
                evidence_ref=f"{claim.warehouse}:{claim.manifest_key}",
            )
        if claim.result_id:
            body = state.open(claim.result_id, chain)
            warehouse, sql, digest = body["w"], body["s"], body["d"]
        else:
            if claim.warehouse is None:
                return _refused(claim, "a statement needs its warehouse")
            warehouse, sql, digest = claim.warehouse, str(claim.sql), ""
        g = guard(sql, warehouse, state.tables(warehouse))
        r = execute(state.warehouse, g, count=False)
        if digest and r.digest != digest:
            return _refused(claim, "re-running the result id returned different rows than the first run")
        column, cell = _cell(r.columns, r.rows, claim.column, claim.row)
    except (BadHandle, Refused, ToolRefusal, TimedOut) as err:
        return _refused(claim, str(err))
    if not isinstance(cell, (int, float)) or isinstance(cell, bool):
        return _refused(claim, f"the cell {column} holds {cell!r}, not a number")
    catalog_unit = state.column_unit(warehouse, g.tables, column)
    if catalog_unit is not None:
        unit, source = catalog_unit, "catalog"
    elif claim.evidence_unit:
        unit, source = claim.evidence_unit, "declared"
    else:
        unit, source = claim.unit, "assumed"
    c = compare(claim.value, claim.unit, float(cell), unit, display=claim.display)
    return ReadbackOut(
        verdict=c.verdict,
        claim=claim.value,
        claim_unit=claim.unit,
        evidence=c.evidence,
        evidence_unit=unit,
        unit_source=source,  # type: ignore[arg-type]
        difference=c.difference,
        tolerance=c.tolerance,
        reason=c.reason,
        evidence_ref=f"{warehouse}:{r.digest[:16]}",
    )


# lookup

KINDS = ("metro", "carrier", "airport", "applicant_group", "aml_rule", "year", "quarter", "county")
KIND_WAREHOUSE = {
    "metro": "doorstep",
    "county": "ledger",
    "carrier": "turnaround",
    "airport": "turnaround",
    "applicant_group": "ledger",
    "aml_rule": "ledger",
}


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def candidates(state: State, kind: str, name: str) -> tuple[str | None, list[LookupCandidate]]:
    """The entity a name resolves to, or the candidates when it names more than one or none."""
    if kind not in KINDS:
        raise ToolRefusal(f"lookup knows the kinds {', '.join(KINDS)}, not {kind!r}")
    q = _norm(name)
    ambiguous = state.entities.get("ambiguous", {})
    for word, spec_ in ambiguous.items():
        if spec_["kind"] == kind and _norm(word) == q and len(spec_["candidates"]) > 1:
            return None, [LookupCandidate(value=c, label=c) for c in spec_["candidates"]]
    if kind == "metro":
        _, rows = state.warehouse.query(
            "select distinct cbsa_title, kind from doorstep.mart_metro_year order by kind, cbsa_title"
        )
        titles = [r[0] for r in rows]
        exact = [t for t in titles if _norm(t) == q]
        if exact:
            return exact[0], []
        first = [t for t in titles if _norm(re.split(r"[-,]", t)[0]) == q]
        metro_first = [t for t, k in rows if t in first and k == "metropolitan"]
        if len(metro_first) == 1:
            return metro_first[0], []
        if len(first) == 1:
            return first[0], []
        if first:
            return None, [LookupCandidate(value=t, label=t) for t in sorted(first)]
        contains = [t for t in titles if q and q in _norm(t)]
        if len(contains) == 1:
            return contains[0], []
        pool = contains or difflib.get_close_matches(name, titles, n=5, cutoff=0.4)
        return None, [LookupCandidate(value=t, label=t) for t in pool[:8]]
    if kind in {"carrier", "airport", "applicant_group", "aml_rule"}:
        table = {"carrier": "carriers", "airport": "airports", "applicant_group": "applicant_groups", "aml_rule": "aml_rules"}[kind]
        names: dict[str, list[str]] = state.entities.get(table, {})
        for code, aliases in names.items():
            if _norm(str(code)) == q or any(_norm(a) == q for a in aliases):
                return str(code), []
        if kind == "airport" and re.fullmatch(r"[A-Za-z]{3}", name.strip()):
            code = name.strip().upper()
            hit = state.warehouse.scalar("select count(*) from turnaround.mart_airport_day where airport = ?", [code])
            if hit:
                return code, []
        pool = difflib.get_close_matches(name, [a for v in names.values() for a in v] + [str(k) for k in names], n=5, cutoff=0.5)
        return None, [LookupCandidate(value=p, label=p) for p in pool]
    if kind == "year":
        m = re.search(r"(19|20)\d\d", name)
        return (m.group(0), []) if m else (None, [])
    if kind == "quarter":
        m = re.search(r"((?:19|20)\d\d)\s*q\s*([1-4])", name.lower())
        if m:
            return f"{m.group(1)}Q{m.group(2)}", []
        words = {"first": 1, "second": 2, "third": 3, "fourth": 4}
        m2 = re.search(r"(first|second|third|fourth) quarter of ((?:19|20)\d\d)", name.lower())
        return (f"{m2.group(2)}Q{words[m2.group(1)]}", []) if m2 else (None, [])
    _, rows = state.warehouse.query("select distinct county, cast(county_fips as varchar) from ledger.f03_county order by 1")
    for county, fips in rows:
        if _norm(str(county)) == q or str(fips) == name.strip():
            return str(fips), []
    return None, [LookupCandidate(value=str(f), label=str(c)) for c, f in rows if q and q in _norm(str(c))]


def lookup_result(kind: str, name: str, resolved: str | None, cands: list[LookupCandidate], asked: bool) -> LookupOut:
    return LookupOut(
        kind=kind,
        query=name,
        resolved=resolved,
        warehouse=KIND_WAREHOUSE.get(kind),  # type: ignore[arg-type]
        needs_choice=resolved is None and len(cands) > 1 and not asked,
        candidates=cands,
    )


def published_display(value: float, fmt: str) -> str:
    return format_value(value, fmt)


def tolerance_of(fmt: str) -> float | None:
    step = spec(fmt).step
    return None if step is None else step / 2
