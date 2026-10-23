"""The input and output schema of every tool. The agent imports these same models, so there is one
definition of each: the server validates against them and the client parses with them."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from readback_core.statements import STATEMENT

WarehouseName = Literal["doorstep", "turnaround", "ledger"]


class Out(BaseModel):
    """Every tool result carries the statement."""

    model_config = ConfigDict(extra="forbid")
    statement: str = STATEMENT


class WarehouseInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: WarehouseName
    repository: str
    tag: str
    commit: str
    tables: int
    rows: int
    metrics: int
    manifest_values: int
    as_of: str
    covers: str


class WarehousesOut(Out):
    warehouses: list[WarehouseInfo]


class ColumnOut(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    type: str
    role: str
    unit: str | None
    definition: str | None
    cited: str | None = Field(
        default=None, description="file:line of the definition in the build, when lifted"
    )


class DescribeOut(Out):
    warehouse: WarehouseName
    table: str
    grain: list[str]
    rows: int
    source_step: str
    columns: list[ColumnOut]
    manifest_keys: list[str]
    examples: list[dict[str, Any]] = Field(description="the first five rows sorted by the grain")


class SearchHit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["table", "column", "metric", "manifest", "definition"]
    warehouse: WarehouseName
    name: str
    unit: str | None
    definition: str | None
    score: float


class SearchOut(Out):
    query: str
    expanded: list[str]
    hits: list[SearchHit]


class SqlColumn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    type: str
    unit: str | None


class RunSqlOut(Out):
    warehouse: WarehouseName
    sql: str = Field(description="the statement as it ran, normalized, with the limit applied")
    columns: list[SqlColumn]
    rows: list[list[Any]]
    row_count: int = Field(description="rows the statement returns before the limit")
    limit: int
    elapsed_ms: float
    digest: str
    result_id: str = Field(description="a handle for readback in the same request chain")


class PublishedValue(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str
    value: float | None
    text: str | None
    display: str
    unit: str
    rounding: float | None = Field(description="the published rounding step in the stored unit")
    low: float | None
    high: float | None
    population: str
    table: str | None
    sql: str | None


class PublishedOut(Out):
    warehouse: WarehouseName
    pattern: str
    matches: int
    values: list[PublishedValue]


class Claim(BaseModel):
    """A number the caller is about to say, and where it says the number came from."""

    model_config = ConfigDict(extra="forbid")
    value: float
    unit: str = Field(
        description="the unit of the value as claimed: fraction, percent, dollars, count, minutes ..."
    )
    display: str | None = Field(default=None, description="the number as it will be shown, e.g. 26.5%")
    warehouse: WarehouseName | None = None
    result_id: str | None = Field(default=None, description="from an earlier run_sql in the same chain")
    sql: str | None = Field(default=None, description="a statement to run instead of a result id")
    manifest_key: str | None = None
    catalog_key: str | None = Field(
        default=None,
        description="a fact of the catalog: <warehouse>.tables, .rows, .metrics, .manifest_values, or "
        "<warehouse>.<table>.rows; warehouses joined by + are summed, as doorstep+ledger.tables",
    )
    definition_id: str | None = Field(
        default=None,
        description="a definition document from search_catalog, for a number the build's definition prints",
    )
    column: str | None = Field(default=None, description="the result column the value is read from")
    row: int = Field(default=0, ge=0)
    evidence_unit: str | None = Field(
        default=None, description="the unit of a computed result column the catalog does not know"
    )


class ReadbackOut(Out):
    verdict: Literal["agree", "disagree", "unit mismatch", "refused"]
    claim: float
    claim_unit: str
    evidence: float | None
    evidence_unit: str | None
    unit_source: Literal["catalog", "declared", "assumed", "manifest", "none"]
    difference: float | None
    tolerance: float | None
    reason: str
    evidence_ref: str = Field(description="the manifest key, or the digest of the result that was re-run")


class LookupCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: str
    label: str


class LookupOut(Out):
    kind: str
    query: str
    resolved: str | None
    warehouse: WarehouseName | None
    needs_choice: bool = Field(
        description="true when the name matches more than one entity and the client could not be asked"
    )
    candidates: list[LookupCandidate]
