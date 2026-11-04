"""Select and validate a warehouse inventory without hardcoded source names."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from readback_core import paths


def load(root: Path | None = None) -> dict[str, Any]:
    root = root or paths.root()
    selected = Path(os.environ.get("READBACK_WAREHOUSE_LOCK", "data/warehouses.lock.json"))
    path = selected if selected.is_absolute() else root / selected
    lock: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    if lock.get("version") != 1 or not lock.get("warehouses"):
        raise ValueError("A nonempty version one warehouse lock is required")
    for name, warehouse in lock["warehouses"].items():
        if not re.fullmatch(r"[a-z][a-z0-9_]*", name):
            raise ValueError("Invalid warehouse name")
        names: set[str] = set()
        for entry in [*warehouse["tables"], *warehouse["documents"]]:
            part = Path(entry["path"])
            if part.is_absolute() or ".." in part.parts or "\\" in entry["path"]:
                raise ValueError("Locked paths must be relative and contained")
            if not re.fullmatch(r"[a-f0-9]{64}", entry["sha256"]):
                raise ValueError("Every locked file needs a SHA-256 digest")
            if "table" in entry:
                table = entry["table"]
                if not re.fullmatch(r"[a-z][a-z0-9_]*", table) or table in names:
                    raise ValueError("Invalid or duplicate table name")
                names.add(table)
    return lock


def names(root: Path | None = None) -> tuple[str, ...]:
    return tuple(sorted(load(root)["warehouses"]))


def validate_name(name: str) -> str:
    if name not in names():
        raise ValueError("Warehouse is not present in the selected lock")
    return name
