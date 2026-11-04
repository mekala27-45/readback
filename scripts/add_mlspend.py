"""Generate a separate combined lock from a pinned MLSpend checkout and its published catalog."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def add(source: Path, commit: str, root: Path = ROOT) -> Path:
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source, text=True).strip()
    if head != commit or len(commit) != 40:
        raise ValueError("MLSpend checkout does not match the pinned source commit")
    lock = json.loads((root / "data/warehouses.lock.json").read_text(encoding="utf-8"))
    published = json.loads((source / "exports/readback/tables.lock.json").read_text(encoding="utf-8"))
    showback = next(row for row in published["tables"] if row["table"] == "showback")
    entries = []
    for rel in ("exports/readback/showback.csv", "exports/readback/consumer-catalog.json"):
        data = (source / rel).read_bytes()
        committed = subprocess.check_output(["git", "show", f"{commit}:{rel}"], cwd=source)
        if data != committed:
            raise ValueError("Source bytes differ from the pinned Git commit")
        digest = hashlib.sha256(data).hexdigest()
        if rel == showback["path"] and digest != showback["sha256"]:
            raise ValueError("MLSpend table differs from its published digest")
        target = root / "data/warehouses/mlspend" / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / rel, target)
        entries.append({"path": rel, "sha256": digest, "bytes": len(data)})
    lock["warehouses"]["mlspend"] = {
        "repository": "https://github.com/mekala27-45/mlspend",
        "tag": commit,
        "commit": commit,
        "external_catalog": entries[1]["path"],
        "tables": [{**entries[0], "table": "showback"}],
        "documents": [entries[1]],
    }
    output = root / "data/warehouses.mlspend.lock.json"
    output.write_text(json.dumps(lock, indent=1) + "\n", encoding="utf-8")
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--commit", required=True)
    args = parser.parse_args()
    print(add(args.source.resolve(), args.commit))
