"""The warehouse: DuckDB over the fetched tables, three schemas, nothing writable.

Each warehouse is a schema of views over its fetched parquet and CSV files. The database itself is
an in memory catalog of views and nothing else; after the views are created the connection is
locked: external access and extension loading are switched off, so a statement cannot read a file
the lock does not name, write a file, attach a database or load an extension, whatever the guard
lets through. The guard in readback_warehouse.guard is the first line; this is the second.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Any

import duckdb
from readback_core import paths

WAREHOUSES: tuple[str, ...] = ("doorstep", "turnaround", "ledger")


class WarehouseMissing(RuntimeError):
    pass


def _reader(path: Path) -> str:
    p = str(path).replace("'", "''")
    if path.suffix == ".parquet":
        return f"read_parquet('{p}')"
    return f"read_csv('{p}', header = true, sample_size = -1)"


def _build_views(db: Path, base: Path, lock: dict[str, Any], extra: dict[tuple[str, str], Path]) -> None:
    con = duckdb.connect(str(db))
    try:
        for name in WAREHOUSES:
            con.execute(f'create schema if not exists "{name}"')
            for t in lock["warehouses"][name]["tables"]:
                path = base / name / t["path"]
                if not path.exists():
                    raise WarehouseMissing(f"{name}: {t['path']} is not on disk; run make fetch")
                con.execute(f'create or replace view "{name}"."{t["table"]}" as select * from {_reader(path)}')
        for (schema, table), path in sorted(extra.items()):
            con.execute(f'create or replace view "{schema}"."{table}" as select * from {_reader(path)}')
    finally:
        con.close()


def open_warehouse(
    root: Path | None = None, base: Path | None = None, extra: dict[tuple[str, str], Path] | None = None
) -> duckdb.DuckDBPyConnection:
    """A read only connection with the three schemas, locked against files, extensions and attachment.

    `extra` adds views that are not in the lock; only the red team fixture uses it.

    The views are written once into a small database file of views, which is then opened read only:
    no statement can create, alter or drop anything. The views read their files lazily, so the files
    the lock names stay readable and nothing else does: external access goes off with an allow list
    of exactly those paths, and the configuration is locked so a statement cannot turn it back on.
    """
    root = root or paths.root()
    base = (base or paths.warehouses_dir()).resolve()
    lock = json.loads((root / "data" / "warehouses.lock.json").read_text(encoding="utf-8"))
    folder = Path(os.environ.get("READBACK_CACHE", tempfile.gettempdir())) / "readback"
    folder.mkdir(parents=True, exist_ok=True)
    db = folder / f"views-{os.getpid()}-{threading.get_ident()}.duckdb"
    if db.exists():
        db.unlink()
    extra = extra or {}
    _build_views(db, base, lock, extra)
    allowed = sorted(str(base / n / t["path"]) for n in WAREHOUSES for t in lock["warehouses"][n]["tables"])
    allowed += sorted(str(p.resolve()) for p in extra.values())
    con = duckdb.connect(
        str(db),
        read_only=True,
        config={
            "autoinstall_known_extensions": False,
            "autoload_known_extensions": False,
            "allow_community_extensions": False,
        },
    )
    con.execute("set allowed_paths = ?", [allowed])
    con.execute("set enable_external_access = false")
    con.execute("set lock_configuration = true")
    return con


class Warehouse:
    """One locked connection per process, with a cursor per call so concurrent requests do not share state."""

    _lock = threading.Lock()
    _shared: Warehouse | None = None

    def __init__(self, con: duckdb.DuckDBPyConnection) -> None:
        self.con = con

    @classmethod
    def shared(cls) -> Warehouse:
        with cls._lock:
            if cls._shared is None:
                cls._shared = cls(open_warehouse())
            return cls._shared

    def cursor(self) -> duckdb.DuckDBPyConnection:
        return self.con.cursor()

    def query(self, sql: str, params: list[Any] | None = None) -> tuple[list[str], list[tuple[Any, ...]]]:
        cur = self.cursor()
        rel = cur.execute(sql, params or [])
        cols = [d[0] for d in rel.description or []]
        return cols, rel.fetchall()

    def scalar(self, sql: str, params: list[Any] | None = None) -> Any:
        _, rows = self.query(sql, params)
        return rows[0][0] if rows else None
