"""Write data/warehouses.lock.json from the three repositories at their tags.

Run once when a tag moves. It lists the files each build publishes at its tag, takes the SHA-256 of
each blob, and records the tag, the commit and the table name each file is served as. The fetch
reads this file and nothing else, so what the server can query is fixed by a committed list.

    python scripts/lock_warehouses.py --doorstep ../doorstep --turnaround ../turnaround --ledger ../ledger
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OWNER = "mekala27-45"
TAG = "v0.1.0"

# What each build publishes, as git pathspecs at the tag, and how a path becomes a table name.
RULES: dict[str, dict[str, object]] = {
    "doorstep": {
        "tables": ["results/marts/*.parquet", "exports/csv/*.csv"],
        "skip": {
            # The whole metro year mart as a 12 MB CSV for spreadsheet users; the parquet is the same table.
            "exports/csv/mart_metro_year.csv",
            "exports/csv/data_dictionary.csv",
            "exports/csv/metrics_definitions.csv",
        },
        "documents": [
            "results/manifest.json",
            "docs/definitions.md",
            "exports/csv/data_dictionary.csv",
            "exports/csv/metrics_definitions.csv",
            "LICENSE",
        ],
    },
    "turnaround": {
        "tables": ["results/marts/*.parquet", "exports/csv/*.csv"],
        "skip": {"exports/csv/dictionary.csv", "exports/csv/metrics_definitions.csv"},
        "documents": [
            "results/manifest.json",
            "docs/definitions.md",
            "exports/csv/dictionary.csv",
            "exports/csv/metrics_definitions.csv",
            "LICENSE",
        ],
    },
    "ledger": {
        "tables": [
            "results/*.parquet",
            "results/*/*.parquet",
            "results/*/*/*.parquet",
            "results/exports/extracts/*.csv",
        ],
        "skip": set(),
        "documents": ["results/manifest.json", "docs/definitions.md", "metrics/bank.yaml", "LICENSE"],
    },
}


def table_name(warehouse: str, path: str) -> str:
    p = Path(path)
    stem = p.stem.lower().replace("-", "_")
    if warehouse in {"doorstep", "turnaround"}:
        return stem if p.suffix == ".parquet" else f"export_{stem}"
    parts = list(p.parts[1:-1])  # drop results/
    if parts[:2] == ["exports", "extracts"]:
        return f"extract_{stem}"
    return "_".join([*parts, stem]).lower()


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout


def blob_sha256(repo: Path, path: str) -> tuple[str, int]:
    data = subprocess.run(
        ["git", "-C", str(repo), "show", f"{TAG}:{path}"], check=True, capture_output=True
    ).stdout
    return hashlib.sha256(data).hexdigest(), len(data)


def lock_one(name: str, repo: Path) -> dict[str, object]:
    rules = RULES[name]
    commit = git(repo, "rev-parse", f"{TAG}^{{commit}}").strip()
    listed = git(repo, "ls-tree", "-r", "--name-only", TAG).splitlines()
    import fnmatch

    tables = []
    for path in listed:
        if path in rules["skip"]:  # type: ignore[operator]
            continue
        if not any(
            fnmatch.fnmatchcase(path, pat) and path.count("/") == pat.count("/") for pat in rules["tables"]
        ):  # type: ignore[attr-defined]
            continue
        digest, size = blob_sha256(repo, path)
        tables.append({"path": path, "table": table_name(name, path), "sha256": digest, "bytes": size})
    names = [t["table"] for t in tables]
    if len(names) != len(set(names)):
        raise SystemExit(f"{name}: two files map to one table name")
    documents = []
    for path in rules["documents"]:  # type: ignore[attr-defined]
        if path not in listed:
            raise SystemExit(f"{name}: {path} is not in the repository at {TAG}")
        digest, size = blob_sha256(repo, path)
        documents.append({"path": path, "sha256": digest, "bytes": size})
    return {
        "repository": f"https://github.com/{OWNER}/{name}",
        "tag": TAG,
        "commit": commit,
        "tables": sorted(tables, key=lambda t: str(t["table"])),
        "documents": documents,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    for name in RULES:
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    lock = {"version": 1, "warehouses": {name: lock_one(name, getattr(args, name)) for name in RULES}}
    out = ROOT / "data" / "warehouses.lock.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(lock, indent=1) + "\n", encoding="utf-8")
    for name, w in lock["warehouses"].items():  # type: ignore[attr-defined]
        print(
            f"{name}: {len(w['tables'])} tables, "
            f"{sum(t['bytes'] for t in w['tables']) / 1e6:.1f} MB at {w['commit'][:7]}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
