"""Load a published catalog whose table identities and bytes are explicitly locked."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

import duckdb
from readback_catalog.model import WarehouseCatalog


def load_external(root: Path, warehouse: str, lock: dict[str, Any]) -> WarehouseCatalog:
    base = (root / "data/warehouses" / warehouse).resolve()
    entries = {row["path"]: row for row in [*lock["tables"], *lock["documents"]]}
    catalog_path = lock["external_catalog"]
    if catalog_path not in entries:
        raise ValueError("External catalog must be named in the file lock")
    for rel, entry in entries.items():
        path = (base / rel).resolve()
        if not path.is_relative_to(base) or hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
            raise ValueError("External warehouse file is outside its root or changed")
    raw = json.loads((base / catalog_path).read_text(encoding="utf-8"))
    catalog = WarehouseCatalog.model_validate(
        {
            **raw,
            "repository": lock["repository"],
            "tag": lock["tag"],
            "commit": lock["commit"],
        }
    )
    if catalog.warehouse != warehouse or {t.name for t in catalog.tables} != {
        t["table"] for t in lock["tables"]
    }:
        raise ValueError("Catalog warehouse or table identity differs from lock")
    con = duckdb.connect()
    try:
        for table in catalog.tables:
            entry = next(t for t in lock["tables"] if t["table"] == table.name)
            if table.path != entry["path"] or any(
                not re.fullmatch(r"[a-z][a-z0-9_]*", c.name) for c in table.columns
            ):
                raise ValueError("Catalog path or column identifier is invalid")
            file = str(base / table.path).replace("'", "''")
            reader = f"read_csv('{file}',header=true,sample_size=-1)"
            desc = con.execute(f"SELECT * FROM {reader} LIMIT 0").description
            assert desc is not None
            if [(name, str(dtype)) for name, dtype, *_ in desc] != [(c.name, c.type) for c in table.columns]:
                raise ValueError("Catalog column types differ from source")
            counted = con.execute(f"SELECT COUNT(*) FROM {reader}").fetchone()
            assert counted is not None
            if counted[0] != table.rows:
                raise ValueError("Catalog row count differs from source")
            if table.grain_unique:
                if not table.grain or any(k not in {c.name for c in table.columns} for k in table.grain):
                    raise ValueError("Invalid grain")
                keys = ",".join(f'"{k}"' for k in table.grain)
                distinct = con.execute(
                    f"SELECT COUNT(*) FROM (SELECT DISTINCT {keys} FROM {reader})"
                ).fetchone()
                assert distinct is not None
                if distinct[0] != table.rows:
                    raise ValueError("Declared table grain is not unique")
        # External metric SQL is data, not executable catalog-build code. Table queries
        # still go through the normal SQL guard and numeric readback gate at runtime.
        catalog.metrics = []
        return catalog
    finally:
        con.close()
