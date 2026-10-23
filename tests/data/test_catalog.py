"""The catalog: every locked table cataloged, every measure column with a unit, the quarantine named."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from readback_catalog.index import Doc, Index, Synonyms
from readback_catalog.model import WarehouseCatalog
from readback_core.units import UNITS, UnitMismatch, convert

ROOT = Path(__file__).resolve().parents[2]


def catalogs() -> list[WarehouseCatalog]:
    out = []
    for name in ("doorstep", "turnaround", "ledger"):
        text = (ROOT / "catalog" / f"{name}.yaml").read_text(encoding="utf-8")
        out.append(WarehouseCatalog.model_validate(yaml.safe_load(text)))
    return out


def quarantine() -> dict[str, object]:
    return json.loads((ROOT / "catalog/quarantine.json").read_text())


def test_every_locked_table_has_a_catalog_entry() -> None:
    lock = json.loads((ROOT / "data/warehouses.lock.json").read_text())
    for c in catalogs():
        locked = {t["table"] for t in lock["warehouses"][c.warehouse]["tables"]}
        assert locked == {t.name for t in c.tables}


def test_every_measure_column_has_a_unit_and_a_definition_or_a_quarantine_row() -> None:
    rows = quarantine()["rows"]  # type: ignore[index]
    flagged = {(r["warehouse"], r["subject"]) for r in rows}  # type: ignore[index]
    for c in catalogs():
        for t in c.tables:
            for col in t.columns:
                if col.role != "measure":
                    continue
                subject = (c.warehouse, f"{t.name}.{col.name}")
                assert col.unit in UNITS or subject in flagged
                assert col.definition is not None or subject in flagged


def test_every_definition_from_a_document_cites_a_line() -> None:
    for c in catalogs():
        for t in c.tables:
            for col in t.columns:
                if col.definition_source in {"definitions", "metrics"}:
                    assert col.citation is not None and col.citation.line > 0


def test_the_quarantine_is_counted_by_warehouse_and_rule() -> None:
    q = quarantine()
    total = sum(n for rules in q["counts"].values() for n in rules.values())  # type: ignore[union-attr]
    assert total == len(q["rows"])  # type: ignore[arg-type]


def test_manifest_index_resolves_every_numeric_value() -> None:
    import pyarrow.parquet as pq

    rows = pq.read_table(ROOT / "catalog/manifest_index.parquet").to_pylist()
    for warehouse in ("doorstep", "turnaround", "ledger"):
        data = json.loads((ROOT / "data/warehouses" / warehouse / "results/manifest.json").read_text())
        keys = {r["key"] for r in rows if r["warehouse"] == warehouse}
        assert keys == set(data["values"])


def test_lexical_index_returns_the_planted_synonym() -> None:
    docs = [Doc("d.t.value_anchored", "column", "doorstep", "t.value_anchored", "value anchored median home", "dollars", None),
            Doc("d.t.rate", "column", "doorstep", "t.rate", "rate mortgage", "percent", None)]
    index = Index(docs)
    expanded = Synonyms({"house price": ["value anchored"]}).expand("what was the house price")
    hits = index.search(expanded, 5)
    assert hits[0].doc.id == "d.t.value_anchored"


def test_a_synonym_that_maps_to_nothing_is_named() -> None:
    index = Index([Doc("a", "table", "doorstep", "a", "payment share", None, None)])
    assert Synonyms({"vibes": ["nothing here"]}).unmapped(index.vocabulary) == ["vibe"]


def test_the_index_refuses_no_documents() -> None:
    with pytest.raises(ValueError, match="no documents"):
        Index([])


def test_a_fraction_against_a_percent_converts_and_a_dollar_does_not() -> None:
    assert convert(0.265, "fraction", "percent") == pytest.approx(26.5)
    assert convert(26.5, "percent", "fraction") == pytest.approx(0.265)
    with pytest.raises(UnitMismatch):
        convert(0.265, "fraction", "dollars")
