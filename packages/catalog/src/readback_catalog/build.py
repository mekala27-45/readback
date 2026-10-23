"""Build the catalog of the three warehouses from the fetched tables and documents.

What it writes, all under catalog/:
  <warehouse>.yaml        one entry per table and column, and the metrics
  manifest_index.parquet  every value of the three manifests with its unit and rounding
  index.parquet           the BM25 documents
  quarantine.json         every rule that fired, by warehouse, named and counted

Nothing is recomputed from raw data. The tables are read for their schema, their row count, their
grain and the range of a column whose unit is a fraction; the definitions come from the documents
each build published, from the data dictionaries, from ledger's metric file, or from the committed
hand edits in catalog/overrides.yaml. A column none of these covers goes to the quarantine.
"""

from __future__ import annotations

import csv
import json
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from readback_core.units import SPECS, Unit, spec

from readback_catalog.definitions import Entry, by_term, parse
from readback_catalog.index import Doc, Index, Synonyms
from readback_catalog.model import (
    Citation,
    Column,
    DefinitionSource,
    Metric,
    QuarantineRow,
    Role,
    TableEntry,
    WarehouseCatalog,
)

NUMERIC = (
    "TINYINT",
    "SMALLINT",
    "INTEGER",
    "BIGINT",
    "HUGEINT",
    "UTINYINT",
    "USMALLINT",
    "UINTEGER",
    "UBIGINT",
    "FLOAT",
    "DOUBLE",
    "DECIMAL",
    "REAL",
)
TIME_TYPES = ("DATE", "TIMESTAMP", "TIME")
# Tables this large are counted but their grain is not tested by a distinct count, which would
# take minutes on a laptop; the grain is stated from the build's own documentation instead.
GRAIN_TEST_LIMIT = 3_000_000
STATED_GRAINS = {
    ("doorstep", "grain_loans"): ["one row per originated loan in the extract"],
    ("doorstep", "grain_acs"): ["year", "cbsa_code", "table", "variable"],
    ("doorstep", "mart_borrowers_income"): ["year", "cbsa_code", "lei", "income_bin"],
}
AS_OF = {"doorstep": "2026Q2", "turnaround": "2026-07", "ledger": "2026-08-31"}
COVERS = {
    "doorstep": (
        "393 metros from 2000 to 2026Q2 in the price index, census years 2005 to 2024, HMDA 2018 to 2025"
    ),
    "turnaround": "every scheduled domestic flight from January 2015 to July 2026, summarized",
    "ledger": "the fictional Harborline Bank, September 2023 to August 2026, with New Jersey HMDA",
}
METRIC_MART = {
    "doorstep": "mart_metro_year",
    "turnaround": "mart_carrier_month",
    "ledger": "metrics_bank_quarter",
}


def norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def source_step(warehouse: str, table: str) -> str:
    if table.startswith("export_"):
        return "the CSV bundle the build exports for spreadsheet users"
    if table.startswith("extract_"):
        return "the extracts the build exports"
    m = re.match(r"ch(\d)_", table)
    if m:
        return f"chapter {m.group(1)} of the story"
    m = re.match(r"f(\d\d)_", table)
    if m:
        return f"function {int(m.group(1))} of the bank"
    for prefix, step in (
        ("calc_", "the affordability calculator"),
        ("misconnect_", "the misconnect calculator"),
        ("rotation_", "the rotation chapter"),
        ("metrics_", "the metric layer"),
        ("models_", "the model registry"),
        ("contracts_", "the data contracts"),
        ("mart_", "the warehouse marts"),
        ("fct_", "the warehouse marts"),
        ("grain_", "the warehouse grain tables"),
    ):
        if table.startswith(prefix):
            return step
    return "the published results"


@dataclass
class Rules:
    patterns: list[tuple[re.Pattern[str] | None, re.Pattern[str], Role, Unit]]

    @classmethod
    def load(cls, path: Path) -> Rules:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        return cls(
            [
                (
                    re.compile(r["table"]) if r.get("table") else None,
                    re.compile(r["pattern"]),
                    r["role"],
                    r["unit"],
                )
                for r in raw["rules"]
            ]
        )

    def match(self, name: str, table: str = "") -> tuple[Role, Unit] | None:
        for table_pattern, pattern, role, unit in self.patterns:
            if table_pattern is not None and not table_pattern.fullmatch(table):
                continue
            if pattern.fullmatch(name):
                return role, unit
        return None


@dataclass
class Sources:
    """The definition sources of one warehouse."""

    warehouse: str
    entries: dict[str, Entry]
    terms: list[tuple[str, list[re.Pattern[str]]]]
    overrides: dict[str, str]
    dictionary: dict[tuple[str, str], dict[str, str]]  # (file stem, normalized column) -> row
    bank_metrics: dict[str, tuple[str, int]] = field(default_factory=dict)  # name -> (definition, line)

    def definition(self, column: str) -> tuple[str, Citation | None, DefinitionSource] | None:
        n = norm(column)
        if n in self.bank_metrics:
            text, line = self.bank_metrics[n]
            return text, Citation(file="metrics/bank.yaml", line=line), "metrics"
        for term, patterns in self.terms:
            if any(p.fullmatch(n) for p in patterns):
                entry = self.entries.get(term)
                if entry is None:
                    raise KeyError(
                        f"{self.warehouse}: definition_terms names {term!r}, absent from the document"
                    )
                return entry.text, Citation(file="docs/definitions.md", line=entry.line), "definitions"
        if n in self.overrides:
            return self.overrides[n], None, "hand edit"
        return None


def _load_dictionary(path: Path) -> dict[tuple[str, str], dict[str, str]]:
    out: dict[tuple[str, str], dict[str, str]] = {}
    if not path.exists():
        return out
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            out[(Path(row["file"]).stem.lower(), norm(row["column"]))] = row
    return out


def _bank_metrics(path: Path) -> dict[str, tuple[str, int]]:
    if not path.exists():
        return {}
    lines = path.read_text(encoding="utf-8").splitlines()
    out: dict[str, tuple[str, int]] = {}
    current: str | None = None
    for i, line in enumerate(lines, start=1):
        m = re.match(r"^  ([a-z_]+):\s*$", line)
        if m:
            current = m.group(1)
            continue
        d = re.match(r"^\s+definition:\s*(.+)$", line)
        if d and current:
            out[current] = (d.group(1).strip().strip('"'), i)
    return out


def load_sources(root: Path, warehouse: str) -> Sources:
    base = root / "data" / "warehouses" / warehouse
    entries = by_term(parse((base / "docs/definitions.md").read_text(encoding="utf-8")))
    terms_raw = yaml.safe_load((root / "catalog/definition_terms.yaml").read_text(encoding="utf-8"))[
        warehouse
    ]
    terms = [(t["term"], [re.compile(c) for c in t["columns"]]) for t in terms_raw]
    overrides = (
        yaml.safe_load((root / "catalog/overrides.yaml").read_text(encoding="utf-8")).get(warehouse, {}) or {}
    )
    dict_path = {
        "doorstep": base / "exports/csv/data_dictionary.csv",
        "turnaround": base / "exports/csv/dictionary.csv",
    }.get(warehouse)
    dictionary = _load_dictionary(dict_path) if dict_path else {}
    return Sources(
        warehouse,
        entries,
        terms,
        {norm(k): v for k, v in overrides.items()},
        dictionary,
        _bank_metrics(base / "metrics/bank.yaml"),
    )


def _reader(path: str) -> str:
    return f"read_parquet('{path}')" if path.endswith(".parquet") else f"read_csv('{path}', header=true)"


def _grain(con: Any, rel: str, rows: int, keys: list[str]) -> tuple[list[str], bool]:
    if rows == 0 or not keys:
        return keys, False
    for n in range(1, len(keys) + 1):
        cols = ", ".join(f'"{k}"' for k in keys[:n])
        distinct = con.execute(f"select count(*) from (select distinct {cols} from {rel})").fetchone()[0]
        if distinct == rows:
            return keys[:n], True
    return keys, False


def build_warehouse(
    root: Path, warehouse: str, lock: dict[str, Any], rules: Rules, quarantine: list[QuarantineRow]
) -> WarehouseCatalog:
    import duckdb

    con = duckdb.connect()
    sources = load_sources(root, warehouse)
    tables: list[TableEntry] = []
    q = quarantine.append
    for t in lock["tables"]:
        path = str(root / "data" / "warehouses" / warehouse / t["path"])
        rel = _reader(path)
        desc = con.execute(f"select * from {rel} limit 0").description
        counted = con.execute(f"select count(*) from {rel}").fetchone()
        assert counted is not None  # a count always returns one row
        rows = int(counted[0])
        columns: list[Column] = []
        stem = Path(t["path"]).stem.lower()
        previous_measure: Column | None = None
        units_by_name: dict[str, tuple[Role, Unit]] = {}
        for name, dtype, *_ in desc:
            ty = str(dtype).upper()
            n = norm(name)
            role: Role
            unit: Unit | None
            dict_row = sources.dictionary.get((stem, n)) if t["table"].startswith("export_") else None
            if dict_row and dict_row.get("format") in SPECS:
                s = spec(dict_row["format"])
                role = (
                    "measure"
                    if s.numeric
                    else ("time" if dict_row["format"] in {"year", "quarter"} else "label")
                )
                unit = s.unit
            elif ty.endswith("]") or ty.startswith(("STRUCT", "MAP", "LIST")):
                role, unit = "label", "none"
            elif any(ty.startswith(k) for k in TIME_TYPES):
                role, unit = "time", "none"
            elif not any(ty.startswith(k) for k in NUMERIC):
                role, unit = ("label" if "VARCHAR" in ty or "BOOL" in ty else "key"), "none"
            else:
                base = re.sub(r"_(low|high|moe)$", "", n)
                if base != n and base in units_by_name:
                    role, unit = units_by_name[base]
                elif n in {"low", "high"} and previous_measure is not None:
                    role, unit = "measure", previous_measure.unit
                else:
                    hit = rules.match(n, t["table"])
                    if hit is None:
                        role, unit = "measure", None
                        q(
                            QuarantineRow(
                                warehouse=warehouse,
                                rule="column lacks a unit",
                                subject=f"{t['table']}.{name}",
                                detail=f"{ty}: no rule in catalog/unit_rules.yaml matches",
                            )
                        )
                    else:
                        role, unit = hit
            units_by_name[n] = (role, unit or "none")
            found = sources.definition(name)
            definition: str | None
            citation: Citation | None
            dsource: DefinitionSource | None
            if dict_row is not None and found is None:
                definition = (
                    f"{name} in {Path(t['path']).name}: "
                    f"{dict_row.get('population') or dict_row.get('source')}"
                )
                citation = Citation(
                    file=Path(t["path"]).parent.as_posix()
                    + "/"
                    + ("data_dictionary.csv" if warehouse == "doorstep" else "dictionary.csv"),
                    line=0,
                )
                dsource = "dictionary"
            elif found is not None:
                definition, citation, dsource = found
            else:
                definition, citation, dsource = None, None, None
                if role == "measure":
                    q(
                        QuarantineRow(
                            warehouse=warehouse,
                            rule="column lacks a definition",
                            subject=f"{t['table']}.{name}",
                            detail="no dictionary, definitions entry or hand edit",
                        )
                    )
            col = Column(
                name=name,
                type=ty,
                role=role,
                unit=unit,
                definition=definition,
                citation=citation,
                definition_source=dsource,
            )
            columns.append(col)
            if role == "measure":
                previous_measure = col
            if unit == "fraction" and rows and t["bytes"] < 50_000_000:
                bounds = con.execute(f'select min("{name}"), max("{name}") from {rel}').fetchone()
                assert bounds is not None  # an aggregate always returns one row
                lo, hi = bounds
                if lo is not None and (float(lo) < -1.5 or float(hi) > 1.5):
                    q(
                        QuarantineRow(
                            warehouse=warehouse,
                            rule="unit disagrees with the values",
                            subject=f"{t['table']}.{name}",
                            detail=(
                                "the rules say fraction, "
                                f"the values run from {float(lo):.4g} to {float(hi):.4g}"
                            ),
                        )
                    )
        keys = [c.name for c in columns if c.role in {"key", "time", "label"}]
        stated = STATED_GRAINS.get((warehouse, t["table"]))
        if stated is not None:
            grain, unique = stated, False
        elif rows > GRAIN_TEST_LIMIT:
            grain, unique = keys, False
        else:
            grain, unique = _grain(con, rel, rows, keys)
        step = source_step(warehouse, t["table"])
        description = f"{rows:,} rows from {step}, one row per {', '.join(grain) if grain else 'row'}."
        tables.append(
            TableEntry(
                warehouse=warehouse,
                name=t["table"],
                path=t["path"],
                grain=grain,
                grain_unique=unique,
                rows=rows,
                source_step=step,
                description=description,
                columns=columns,
            )
        )
    metrics = build_metrics(root, warehouse, con, tables, quarantine)
    return WarehouseCatalog(
        warehouse=warehouse,
        repository=lock["repository"],
        tag=lock["tag"],
        commit=lock["commit"],
        as_of=AS_OF[warehouse],
        covers=COVERS[warehouse],
        tables=tables,
        metrics=metrics,
    )


def build_metrics(
    root: Path, warehouse: str, con: Any, tables: list[TableEntry], quarantine: list[QuarantineRow]
) -> list[Metric]:
    base = root / "data" / "warehouses" / warehouse
    mart = METRIC_MART[warehouse]
    mart_entry = next(t for t in tables if t.name == mart)
    found: list[tuple[str, str, str, Citation]] = []
    if warehouse in {"doorstep", "turnaround"}:
        path = base / "exports/csv/metrics_definitions.csv"
        with path.open(encoding="utf-8", newline="") as handle:
            reader = csv.reader(handle)
            next(reader)
            for i, row in enumerate(reader, start=2):
                name, _grain, over_mart = row[0], row[1], row[2]
                found.append(
                    (
                        name,
                        f"select {over_mart} as value from {mart}",
                        f"{name}, over the mart",
                        Citation(file="exports/csv/metrics_definitions.csv", line=i),
                    )
                )
    else:
        bank = _bank_metrics(base / "metrics/bank.yaml")
        for name, (definition, line) in sorted(bank.items()):
            found.append(
                (
                    name,
                    f"select period, {name} as value from {mart} order by period",
                    definition,
                    Citation(file="metrics/bank.yaml", line=line),
                )
            )
    out: list[Metric] = []
    marts = [t for t in tables if t.name.startswith(("mart_", "metrics_"))]
    for name, sql, definition, citation in found:
        bound: str | None = None
        error = ""
        # The published SQL names "the mart"; it binds to the shipped mart that carries its columns.
        for candidate in [mart_entry, *[m for m in marts if m.name != mart]]:
            crel = _reader(str(base / candidate.path))
            try:
                con.execute(sql.replace(f"from {mart}", f"from {crel}") + " limit 0")
                bound = candidate.name
                break
            except Exception as exc:  # duckdb raises its own error classes
                error = error or str(exc).splitlines()[0][:160]
        if bound is None:
            quarantine.append(
                QuarantineRow(
                    warehouse=warehouse,
                    rule="metric SQL does not parse against the table",
                    subject=name,
                    detail=error,
                )
            )
        table = bound or mart
        out.append(
            Metric(
                warehouse=warehouse,
                name=name,
                definition=definition,
                sql=sql.replace(f"from {mart}", f"from {table}"),
                table=table,
                citation=citation,
                parses=bound is not None,
            )
        )
    return out


@dataclass(frozen=True)
class ManifestRow:
    warehouse: str
    key: str
    value: float | None
    text: str | None
    fmt: str
    unit: str
    step: float | None
    low: float | None
    high: float | None
    population: str
    source: str


def manifest_rows(root: Path, warehouse: str, quarantine: list[QuarantineRow]) -> list[ManifestRow]:
    data = json.loads(
        (root / "data" / "warehouses" / warehouse / "results/manifest.json").read_text(encoding="utf-8")
    )
    values: dict[str, Any] = data["values"]
    out: list[ManifestRow] = []
    for key in sorted(values):
        v = values[key]
        fmt = v.get("fmt", "")
        if fmt not in SPECS:
            quarantine.append(
                QuarantineRow(
                    warehouse=warehouse,
                    rule="manifest rounding cannot be read",
                    subject=key,
                    detail=f"format {fmt!r} is not in the unit table",
                )
            )
            continue
        s = spec(fmt)
        raw = v.get("value")
        number = float(raw) if isinstance(raw, (int, float)) and not isinstance(raw, bool) else None
        text = None if number is not None else (None if raw is None else str(raw))
        low = high = None
        for lk, hk in ((f"{key}_low", f"{key}_high"), (f"{key}.low", f"{key}.high")):
            if lk in values and hk in values:
                lv, hv = values[lk].get("value"), values[hk].get("value")
                if isinstance(lv, (int, float)) and isinstance(hv, (int, float)):
                    low, high = float(lv), float(hv)
        prov = v.get("provenance", {})
        out.append(
            ManifestRow(
                warehouse=warehouse,
                key=key,
                value=number,
                text=text,
                fmt=fmt,
                unit=s.unit,
                step=s.step if s.numeric else None,
                low=low,
                high=high,
                population=str(prov.get("population") or ""),
                source=str(prov.get("source") or ""),
            )
        )
    return out


def humanize(name: str) -> str:
    return norm(name).replace("_", " ")


def definition_docs(root: Path) -> list[Doc]:
    """Each entry of each build's definitions document, whole paragraph, cited by line."""
    docs: list[Doc] = []
    for warehouse in ("doorstep", "turnaround", "ledger"):
        text = (root / "data/warehouses" / warehouse / "docs/definitions.md").read_text(encoding="utf-8")
        seen: set[str] = set()
        for e in parse(text):
            if e.term in seen or not e.paragraph or (e.term.endswith(".") and len(e.paragraph) < 12):
                continue
            seen.add(e.term)
            term = e.term.rstrip(".")
            docs.append(
                Doc(
                    id=f"{warehouse}.definition.{norm(term)}",
                    kind="definition",
                    warehouse=warehouse,
                    name=f"{term} (docs/definitions.md:{e.line})",
                    text=f"{term} {term} {term} {e.paragraph}",
                    unit=None,
                    definition=e.paragraph,
                )
            )
    return docs


def docs_for(
    catalogs: list[WarehouseCatalog], manifest: list[ManifestRow], root: Path | None = None
) -> list[Doc]:
    docs: list[Doc] = definition_docs(root) if root is not None else []
    for c in catalogs:
        for t in c.tables:
            docs.append(
                Doc(
                    id=f"{c.warehouse}.{t.name}",
                    kind="table",
                    warehouse=c.warehouse,
                    name=t.name,
                    text=(
                        f"{humanize(t.name)} {t.description} "
                        f"{' '.join(humanize(col.name) for col in t.columns)}"
                    ),
                    unit=None,
                    definition=t.description,
                )
            )
            for col in t.columns:
                if col.role != "measure":
                    continue
                docs.append(
                    Doc(
                        id=f"{c.warehouse}.{t.name}.{col.name}",
                        kind="column",
                        warehouse=c.warehouse,
                        name=f"{t.name}.{col.name}",
                        text=(
                            f"{humanize(col.name)} {humanize(col.name)} "
                            f"{humanize(t.name)} {col.definition or ''}"
                        ),
                        unit=col.unit,
                        definition=col.definition,
                    )
                )
        for m in c.metrics:
            docs.append(
                Doc(
                    id=f"{c.warehouse}.metric.{norm(m.name)}",
                    kind="metric",
                    warehouse=c.warehouse,
                    name=m.name,
                    text=f"{m.name} {m.name} {m.definition}",
                    unit=None,
                    definition=m.definition,
                )
            )
    for r in manifest:
        if r.value is None:
            continue
        docs.append(
            Doc(
                id=f"{r.warehouse}.manifest.{r.key}",
                kind="manifest",
                warehouse=r.warehouse,
                name=r.key,
                text=f"{humanize(r.key)} {humanize(r.key)} {r.population}",
                unit=r.unit,
                definition=r.population or None,
            )
        )
    docs.sort(key=lambda d: d.id)
    return docs


def write_catalog(path: Path, catalog: WarehouseCatalog) -> None:
    data = json.loads(catalog.model_dump_json(exclude_none=False))
    path.write_text(
        f"# The catalog of {catalog.warehouse} at {catalog.tag} ({catalog.commit[:7]}), built by\n"
        "# scripts/build_catalog.py from the fetched tables and documents. Do not edit by hand: change\n"
        "# catalog/unit_rules.yaml, catalog/definition_terms.yaml or catalog/overrides.yaml and rebuild.\n"
        + yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=110),
        encoding="utf-8",
    )


def write_manifest_index(path: Path, rows: Iterable[ManifestRow]) -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq

    rows = list(rows)
    cols = {f: [getattr(r, f) for r in rows] for f in ManifestRow.__dataclass_fields__}
    pq.write_table(pa.table(cols), path, compression="zstd")


def build(root: Path) -> dict[str, Any]:
    lock = json.loads((root / "data/warehouses.lock.json").read_text(encoding="utf-8"))
    rules = Rules.load(root / "catalog/unit_rules.yaml")
    quarantine: list[QuarantineRow] = []
    catalogs = [
        build_warehouse(root, w, lock["warehouses"][w], rules, quarantine) for w in sorted(lock["warehouses"])
    ]
    manifest: list[ManifestRow] = []
    for w in sorted(lock["warehouses"]):
        manifest.extend(manifest_rows(root, w, quarantine))
    for c in catalogs:
        locked = {t["table"] for t in lock["warehouses"][c.warehouse]["tables"]}
        present = {t.name for t in c.tables}
        for missing in sorted(locked - present):
            quarantine.append(
                QuarantineRow(
                    warehouse=c.warehouse,
                    rule="locked table absent from the catalog",
                    subject=missing,
                    detail="the lock names it and the build did not catalog it",
                )
            )
    linked = {(r.warehouse, r.key) for r in manifest if r.key.startswith("chart.")}
    for r in manifest:
        if (r.warehouse, r.key) not in linked and r.value is not None:
            # The three manifests record the step that produced a value, not the table it was read from.
            quarantine.append(
                QuarantineRow(
                    warehouse=r.warehouse,
                    rule="manifest key with no table behind it",
                    subject=r.key,
                    detail=f"recorded origin only: {r.source or 'none'}",
                )
            )
    docs = docs_for(catalogs, manifest, root)
    index = Index(docs)
    syn_raw = yaml.safe_load((root / "catalog/synonyms.yaml").read_text(encoding="utf-8"))["synonyms"]
    synonyms = Synonyms(syn_raw)
    for phrase in synonyms.unmapped(index.vocabulary):
        quarantine.append(
            QuarantineRow(
                warehouse="all",
                rule="synonym maps to nothing",
                subject=phrase,
                detail="none of its targets is a word in the catalog",
            )
        )
    out_dir = root / "catalog"
    for c in catalogs:
        write_catalog(out_dir / f"{c.warehouse}.yaml", c)
    write_manifest_index(out_dir / "manifest_index.parquet", manifest)
    index.write(out_dir / "index.parquet")
    quarantine.sort(key=lambda r: (r.warehouse, r.rule, r.subject))
    report = {
        "rows": [json.loads(r.model_dump_json()) for r in quarantine],
        "counts": _counts(quarantine),
    }
    (out_dir / "quarantine.json").write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    return {
        "tables": sum(len(c.tables) for c in catalogs),
        "columns": sum(len(t.columns) for c in catalogs for t in c.tables),
        "metrics": sum(len(c.metrics) for c in catalogs),
        "manifest_values": len(manifest),
        "documents": len(docs),
        "quarantine": len(quarantine),
        "counts": report["counts"],
    }


def _counts(rows: list[QuarantineRow]) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for r in rows:
        out.setdefault(r.warehouse, {}).setdefault(r.rule, 0)
        out[r.warehouse][r.rule] += 1
    return out
