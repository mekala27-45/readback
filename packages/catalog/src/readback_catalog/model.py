"""The catalog schema: what the server says about every table, column, metric and manifest value."""

from __future__ import annotations

from typing import Literal

from pydantic import Field
from readback_core.model import StrictModel
from readback_core.units import Unit

Role = Literal["key", "time", "label", "measure"]
DefinitionSource = Literal["dictionary", "definitions", "metrics", "hand edit"]
WAREHOUSES: tuple[str, ...] = ("doorstep", "turnaround", "ledger")


class Citation(StrictModel):
    file: str
    line: int


class Column(StrictModel):
    name: str
    type: str
    role: Role
    unit: Unit | None
    definition: str | None
    citation: Citation | None = None
    definition_source: DefinitionSource | None = None
    manifest_keys: list[str] = Field(default_factory=list)


class TableEntry(StrictModel):
    warehouse: str
    name: str
    path: str
    grain: list[str]
    grain_unique: bool
    rows: int
    source_step: str
    description: str
    columns: list[Column]

    def column(self, name: str) -> Column | None:
        for c in self.columns:
            if c.name == name:
                return c
        return None


class Metric(StrictModel):
    warehouse: str
    name: str
    definition: str
    sql: str
    table: str
    citation: Citation
    parses: bool


class WarehouseCatalog(StrictModel):
    warehouse: str
    repository: str
    tag: str
    commit: str
    as_of: str
    covers: str
    tables: list[TableEntry]
    metrics: list[Metric]

    def table(self, name: str) -> TableEntry | None:
        for t in self.tables:
            if t.name == name:
                return t
        return None


class QuarantineRow(StrictModel):
    warehouse: str
    rule: str
    subject: str
    detail: str
