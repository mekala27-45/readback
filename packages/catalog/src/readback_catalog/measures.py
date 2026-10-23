"""The measures table (catalog/measures.yaml) and the SQL it compiles to.

The golden set computes its known answers with these functions and the floor answers with the same
ones, so a question about a listed measure has one SQL for its truth and for its answer. A model
writes its own SQL; the gate and the graders do not care which, only whether the number agrees.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from readback_core.model import StrictModel

TimeKind = Literal["year", "quarter", "none"]


class Measure(StrictModel):
    id: str
    warehouse: str
    table: str
    entity: str
    entity_column: str | None
    time: TimeKind
    time_column: str | None
    expr: str
    fmt: str
    unit: str
    phrases: list[str]
    where: str | None = None
    years: list[int] | None = None
    higher: str | None = None


def load(path: Path) -> list[Measure]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return [Measure.model_validate(m) for m in raw["measures"]]


def quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _filters(m: Measure, entity: str | None, time: str | int | None) -> list[str]:
    parts: list[str] = []
    if m.where:
        parts.append(f"({m.where})")
    if m.entity_column and entity is not None:
        parts.append(f"{m.entity_column} = {quote(entity)}")
    if m.time_column and time is not None:
        parts.append(f"{m.time_column} = {time if isinstance(time, int) else quote(str(time))}")
    return parts


def value_sql(m: Measure, entity: str | None, time: str | int | None) -> str:
    """One value of the measure for one entity at one time."""
    where = _filters(m, entity, time)
    clause = f" where {' and '.join(where)}" if where else ""
    return f"select {m.expr} as value from {m.warehouse}.{m.table}{clause}"


def ranking_sql(
    m: Measure, time: str | int | None, k: int, highest: bool, floor: str | None = None, having: str | None = None
) -> str:
    """The top k entities by the measure at a time, ties broken by the entity name.

    floor is a row filter (metros with at least a million households); having is a group filter
    (carriers that flew at least half a million flights in the year).
    """
    if not m.entity_column:
        raise ValueError(f"{m.id} has no entity to rank")
    where = _filters(m, None, time)
    if floor:
        where.append(floor)
    clause = f" where {' and '.join(where)}" if where else ""
    order = "desc" if highest else "asc"
    extra = f" and {having}" if having else ""
    return (
        f"select {m.entity_column} as entity, {m.expr} as value from {m.warehouse}.{m.table}{clause} "
        f"group by {m.entity_column} having {m.expr} is not null{extra} order by value {order}, entity limit {k}"
    )


def period_ranking_sql(m: Measure, k: int, highest: bool, periods: list[str]) -> str:
    """The top k periods by the measure, for a measure with no entity (the bank's quarters)."""
    if not m.time_column:
        raise ValueError(f"{m.id} has no time to rank")
    inlist = ", ".join(quote(p) for p in periods)
    order = "desc" if highest else "asc"
    return (
        f"select {m.time_column} as entity, {m.expr} as value from {m.warehouse}.{m.table} "
        f"where {m.time_column} in ({inlist}) group by {m.time_column} order by value {order}, entity limit {k}"
    )
