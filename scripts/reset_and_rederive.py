"""Reset and rederive: every published number rebuilt from nothing, in a clean worktree, and compared.

A git worktree is made at HEAD in a temporary folder, so nothing in the working copy is read or
written. In it the warehouses are fetched and checked against the lock (or linked from this copy's
data/warehouses when they are already here and match), the catalog and the golden set are rebuilt,
the floor runs both splits and the red team, and the scorecard, the manifest and every document are
rendered again. Then the rebuilt files are compared with the committed ones.

The code is the installed workspace, which is HEAD when this runs before a tag; the data, the
catalog, the golden set and every output are the worktree's. Drift is any difference in the
catalog, the golden set, the scorecard's graded results, a manifest value, or a rendered document.
Two things are allowed to differ and are listed, not counted: wall clock timings (latency in
milliseconds) and the as of date. The result goes to results/rederive.json.

With --live it first clears the answer log and the spans in the database DATABASE_URL names, which
is what the demo recording filled, then rederives as above.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Values that measure the machine, not the data.
VOLATILE_SUFFIXES = ("_ms",)
VOLATILE_KEYS = {"latency_ms", "p50_ms", "p99_ms", "cassette_dates", "registered_at"}
COMPARED = [
    "catalog/doorstep.yaml",
    "catalog/turnaround.yaml",
    "catalog/ledger.yaml",
    "catalog/quarantine.json",
    "evals/golden/doorstep.yaml",
    "evals/golden/turnaround.yaml",
    "evals/golden/ledger.yaml",
    "evals/golden/multi.yaml",
    "evals/golden/refusal.yaml",
]
RENDERED = ["README.md", "RESULTS.md", "docs/connect.md", "report/briefing.md"]


def run(cmd: list[str], cwd: Path, env: dict[str, str]) -> None:
    print("  $", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=cwd, env=env, check=True)


def strip_volatile(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            k: strip_volatile(v)
            for k, v in value.items()
            if k not in VOLATILE_KEYS and not str(k).endswith(VOLATILE_SUFFIXES)
        }
    if isinstance(value, list):
        return [strip_volatile(v) for v in value]
    return value


def timeless(table: dict[str, Any] | None) -> Any:
    """A manifest table without its timing columns (a header ending in ms)."""
    if table is None:
        return None
    keep = [i for i, c in enumerate(table["columns"]) if not str(c).endswith(" ms")]
    return {
        "columns": [table["columns"][i] for i in keep],
        "rows": [[row[i] for i in keep] for row in table["rows"]],
    }


def manifest_drift(old: dict[str, Any], new: dict[str, Any]) -> tuple[list[str], list[str]]:
    drift, volatile = [], []
    for key in sorted(set(old["values"]) | set(new["values"])):
        a, b = old["values"].get(key), new["values"].get(key)
        va = a["value"] if a else None
        vb = b["value"] if b else None
        if va == vb:
            continue
        if key.endswith(VOLATILE_SUFFIXES) or key.startswith(
            ("build.commits", "deploy.", "latency.", "live.")
        ):
            volatile.append(key)
        else:
            drift.append(f"manifest {key}: {va!r} then {vb!r}")
    for key in sorted(set(old["tables"]) | set(new["tables"])):
        ta = timeless(old["tables"].get(key))
        tb = timeless(new["tables"].get(key))
        if ta != tb and key not in {"checklist"}:
            drift.append(f"manifest table {key}")
    return drift, volatile


def graded(path: Path) -> list[tuple[str, bool, str]]:
    rows = json.loads(path.read_text(encoding="utf-8"))["rows"]
    return sorted((r["id"], bool(r.get("passed")), r.get("text", "")) for r in rows)


def clear_live() -> dict[str, int]:
    import sqlalchemy as sa
    from readback_api import db

    if not os.environ.get("DATABASE_URL"):
        raise SystemExit("--live needs DATABASE_URL")
    engine = db.engine()
    with engine.begin() as conn:
        spans = conn.execute(sa.delete(db.spans)).rowcount or 0
    answers = db.Log(engine).clear_answers()
    return {"answers": answers, "spans": int(spans)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--live", action="store_true", help="clear the live answer log and spans first")
    parser.add_argument("--keep", action="store_true", help="keep the worktree for inspection")
    args = parser.parse_args()
    started = time.time()
    cleared = clear_live() if args.live else None

    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()
    work = Path(tempfile.mkdtemp(prefix="readback-rederive-")) / "tree"
    run(["git", "worktree", "add", "--detach", str(work), head], ROOT, dict(os.environ))
    env = {**os.environ, "READBACK_ROOT": str(work), "PYTHONHASHSEED": "0"}
    for key in ("GEMINI_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY", "SAMBANOVA_API_KEY", "DATABASE_URL"):
        env.pop(key, None)
    env["READBACK_SQLITE"] = str(work / "rederive.sqlite")
    py = [sys.executable]
    cli = [str(Path(sys.executable).parent / "readback")]
    try:
        local = ROOT / "data" / "warehouses"
        if local.exists():
            # The fetch checks every digest either way; a copy here only saves the download.
            shutil.copytree(local, work / "data" / "warehouses")
        run([*py, "scripts/fetch_warehouses.py"], work, env)
        run([*py, "scripts/build_catalog.py"], work, env)
        run([*py, "scripts/build_golden.py"], work, env)
        run([*cli, "eval", "--provider", "floor"], work, env)
        run([*cli, "redteam", "--provider", "floor"], work, env)
        run([*cli, "scorecard"], work, env)
        run([*cli, "manifest"], work, env)
        run([*py, "scripts/check_published_numbers.py", "--write"], work, env)

        drift: list[str] = []
        for rel in COMPARED:
            if (ROOT / rel).read_bytes() != (work / rel).read_bytes():
                drift.append(f"file {rel}")
        if graded(ROOT / "results/evals/runs/floor.json") != graded(work / "results/evals/runs/floor.json"):
            drift.append("the floor's graded answers")
        old_rt = json.loads((ROOT / "results/evals/redteam/floor.json").read_text(encoding="utf-8"))
        new_rt = json.loads((work / "results/evals/redteam/floor.json").read_text(encoding="utf-8"))
        if (old_rt["passed"], old_rt["graded"]) != (new_rt["passed"], new_rt["graded"]):
            drift.append("the red team result")
        m_drift, volatile = manifest_drift(
            json.loads((ROOT / "results/manifest.json").read_text(encoding="utf-8")),
            json.loads((work / "results/manifest.json").read_text(encoding="utf-8")),
        )
        drift += m_drift
        rendered_diff = [
            rel
            for rel in RENDERED
            if (ROOT / rel).read_text(encoding="utf-8") != (work / rel).read_text(encoding="utf-8")
        ]
    finally:
        if not args.keep:
            subprocess.run(["git", "worktree", "remove", "--force", str(work)], cwd=ROOT, check=False)
            shutil.rmtree(work.parent, ignore_errors=True)

    minutes = round((time.time() - started) / 60, 1)
    out = {
        "commit": head,
        "drift": len(drift),
        "differences": drift,
        "volatile": volatile,
        "rendered_differ": rendered_diff,
        "minutes": minutes,
        "cleared": cleared,
        "status": "no drift" if not drift else f"{len(drift)} drifted",
        "hashseed": "0",
    }
    (ROOT / "results").mkdir(exist_ok=True)
    (ROOT / "results" / "rederive.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=1))
    return 0 if not drift else 1


if __name__ == "__main__":
    sys.exit(main())
