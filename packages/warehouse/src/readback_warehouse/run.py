"""Run a guarded statement with a timeout, and digest what it returned."""

from __future__ import annotations

import datetime as _dt
import decimal
import math
import threading
import time
from dataclasses import dataclass
from typing import Any

from readback_core.hashing import sha256_json

from readback_warehouse.connection import Warehouse
from readback_warehouse.guard import TIMEOUT_SECONDS, Guarded


class TimedOut(TimeoutError):
    def __init__(self, seconds: float) -> None:
        super().__init__(f"the statement ran past the {seconds:g} second timeout and was stopped")
        self.seconds = seconds


@dataclass(frozen=True)
class Result:
    columns: list[str]
    types: list[str]
    rows: list[list[Any]]
    row_count: int
    elapsed_ms: float
    digest: str


def plain(value: Any) -> Any:
    """A cell as JSON can carry it: dates as ISO strings, decimals as floats, NaN as null."""
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, (_dt.date, _dt.datetime, _dt.time)):
        return value.isoformat()
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    if isinstance(value, dict):
        return {str(k): plain(v) for k, v in value.items()}
    if isinstance(value, bytes):
        return value.hex()
    return value


def digest_rows(columns: list[str], rows: list[list[Any]]) -> str:
    return sha256_json({"columns": columns, "rows": rows})


def execute(warehouse: Warehouse, guarded: Guarded, *, timeout: float = TIMEOUT_SECONDS, count: bool = True) -> Result:
    cur = warehouse.cursor()
    timer = threading.Timer(timeout, cur.interrupt)
    started = time.perf_counter()
    timer.start()
    try:
        rel = cur.execute(guarded.sql)
        columns = [d[0] for d in rel.description or []]
        types = [str(d[1]) for d in rel.description or []]
        rows = [[plain(v) for v in row] for row in rel.fetchall()]
        total = len(rows)
        if count and len(rows) >= guarded.limit:
            total = int(cur.execute(f"select count(*) from ({guarded.unlimited}) as counted").fetchone()[0])  # type: ignore[index]
    except Exception as exc:
        if time.perf_counter() - started >= timeout * 0.95 and "INTERRUPT" in type(exc).__name__.upper() + str(exc).upper():
            raise TimedOut(timeout) from exc
        raise
    finally:
        timer.cancel()
    elapsed = (time.perf_counter() - started) * 1000.0
    return Result(columns, types, rows, total, round(elapsed, 2), digest_rows(columns, rows))
