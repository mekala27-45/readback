"""What the server holds in memory: the catalog, the index, the manifest index and the warehouse.

Loaded once per process. Nothing here changes after start, which is why the list and read results
carry a public cache hint of an hour.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import threading
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import Any

import yaml
from readback_catalog.index import Index, Synonyms
from readback_catalog.measures import Measure
from readback_catalog.measures import load as load_measures
from readback_catalog.model import WarehouseCatalog
from readback_core import paths
from readback_core.hashing import sha256_text
from readback_warehouse.connection import WAREHOUSES, Warehouse


class BadHandle(ValueError):
    pass


@dataclass(frozen=True)
class ManifestEntry:
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


class State:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or paths.root()
        self._lock = threading.Lock()
        self._warehouse: Warehouse | None = None

    # the catalog
    @cached_property
    def catalogs(self) -> dict[str, WarehouseCatalog]:
        out = {}
        for name in WAREHOUSES:
            raw = yaml.safe_load((self.root / "catalog" / f"{name}.yaml").read_text(encoding="utf-8"))
            out[name] = WarehouseCatalog.model_validate(raw)
        return out

    @cached_property
    def index(self) -> Index:
        return Index.read(self.root / "catalog" / "index.parquet")

    @cached_property
    def synonyms(self) -> Synonyms:
        raw = yaml.safe_load((self.root / "catalog" / "synonyms.yaml").read_text(encoding="utf-8"))
        return Synonyms(raw["synonyms"])

    @cached_property
    def entities(self) -> dict[str, Any]:
        data: dict[str, Any] = yaml.safe_load(
            (self.root / "catalog" / "entities.yaml").read_text(encoding="utf-8")
        )
        return data

    @cached_property
    def measures(self) -> list[Measure]:
        return load_measures(self.root / "catalog" / "measures.yaml")

    @cached_property
    def manifest(self) -> dict[str, dict[str, ManifestEntry]]:
        import pyarrow.parquet as pq

        out: dict[str, dict[str, ManifestEntry]] = {w: {} for w in WAREHOUSES}
        for row in pq.read_table(self.root / "catalog" / "manifest_index.parquet").to_pylist():
            out[row["warehouse"]][row["key"]] = ManifestEntry(**row)
        return out

    @cached_property
    def figure_tables(self) -> dict[str, dict[str, list[str]]]:
        """For each warehouse, the manifest figure keys whose published SQL reads each table."""
        import sqlglot
        from sqlglot import exp

        out: dict[str, dict[str, list[str]]] = {w: {} for w in WAREHOUSES}
        for w in WAREHOUSES:
            path = self.warehouse_dir / w / "results" / "manifest.json"
            if not path.exists():
                continue
            figures = json.loads(path.read_text(encoding="utf-8")).get("figures", {})
            names = {t.name for t in self.catalogs[w].tables}
            for key in sorted(figures):
                sql = figures[key].get("sql")
                if not sql:
                    continue
                try:
                    tables = {
                        str(t.name).lower() for t in sqlglot.parse_one(sql, read="duckdb").find_all(exp.Table)
                    }
                except Exception:  # a figure's SQL in another dialect simply links nothing
                    continue
                for t in sorted(tables & names):
                    out[w].setdefault(t, []).append(key)
        return out

    @property
    def warehouse_dir(self) -> Path:
        return paths.warehouses_dir()

    @property
    def warehouse(self) -> Warehouse:
        with self._lock:
            if self._warehouse is None:
                self._warehouse = Warehouse.shared()
            return self._warehouse

    def tables(self, warehouse: str) -> list[str]:
        return [t.name for t in self.catalogs[warehouse].tables]

    def column_unit(self, warehouse: str, tables: tuple[str, ...], column: str) -> str | None:
        """The catalog unit of a result column, when it names a column of a table the query read."""
        found: set[str] = set()
        for name in tables:
            entry = self.catalogs[warehouse].table(name)
            if entry is None:
                continue
            col = entry.column(column)
            if col is not None and col.unit is not None and col.role == "measure":
                found.add(col.unit)
        return found.pop() if len(found) == 1 else None

    # result handles: stateless, integrity checked, carrying the statement itself
    @cached_property
    def _handle_key(self) -> bytes:
        configured = os.environ.get("READBACK_RESULT_KEY")
        if configured:
            return configured.encode()
        lock = (self.root / "data" / "warehouses.lock.json").read_text(encoding="utf-8")
        return hashlib.sha256(("readback result handle " + sha256_text(lock)).encode()).digest()

    def mint(self, warehouse: str, sql: str, digest: str, chain: str) -> str:
        body = json.dumps(
            {"w": warehouse, "s": sql, "d": digest, "c": chain}, separators=(",", ":"), sort_keys=True
        )
        payload = base64.urlsafe_b64encode(body.encode()).decode().rstrip("=")
        mac = hmac.new(self._handle_key, payload.encode(), hashlib.sha256).hexdigest()[:24]
        return f"r1.{payload}.{mac}"

    def open(self, handle: str, chain: str) -> dict[str, str]:
        try:
            version, payload, mac = handle.split(".")
        except ValueError as err:
            raise BadHandle("the result id is not one this server minted") from err
        if version != "r1":
            raise BadHandle("the result id is from another version of the server")
        expected = hmac.new(self._handle_key, payload.encode(), hashlib.sha256).hexdigest()[:24]
        if not hmac.compare_digest(mac, expected):
            raise BadHandle("the result id was altered or was minted by another server")
        body: dict[str, str] = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        if body["c"] != chain:
            raise BadHandle("the result id belongs to another request chain")
        return body


_STATE: State | None = None
_STATE_LOCK = threading.Lock()


def shared_state() -> State:
    global _STATE
    with _STATE_LOCK:
        if _STATE is None:
            _STATE = State()
        return _STATE
