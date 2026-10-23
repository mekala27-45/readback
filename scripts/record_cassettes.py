"""Grade one provider live, a slice at a time, inside its free daily budget, and keep the cassettes.

The live eval is incremental. Each run takes the test questions (then the development questions)
the provider has not been graded on yet, as many as its budget allows, calls the model with
READBACK_CASSETTES=record so every request and response is stored under evals/cassettes, and merges
the new rows into results/evals/runs/<provider>.json. A question already graded is never asked
again; CI replays its cassette instead. The scorecard reports the share graded, so a partial run is
labeled partial and never extrapolated.

The budget guard: a turn makes at most three model calls (the draft, one repair, one structured
retry), so a run asks at most a third of the provider's daily budget in questions, less what the
ledger says was used today, and stops early on the first BudgetSpent.

  uv run python scripts/record_cassettes.py --provider gemini
  uv run python scripts/record_cassettes.py --provider groq --limit 10
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

CALLS_PER_TURN = 3


def plan(provider: str, limit: int | None) -> tuple[list[Any], dict[str, Any] | None, int]:
    from readback_core import paths
    from readback_evals.golden import load
    from readback_providers import registry

    known = {p.name: p for p in registry.load()}
    if provider not in known or provider == "floor":
        raise SystemExit(f"no live provider named {provider}")
    p = known[provider]
    if not p.has_key():
        raise SystemExit(f"{provider} has no key in the environment; nothing to record")
    run_path = paths.results_dir() / "evals" / "runs" / f"{provider}.json"
    previous = json.loads(run_path.read_text(encoding="utf-8")) if run_path.exists() else None
    done = {r["id"] for r in (previous or {}).get("rows", []) if r.get("graded")}
    golden = load(paths.evals_dir() / "golden")
    todo = [q for q in golden if q.split == "test" and q.id not in done]
    todo += [q for q in golden if q.split == "dev" and q.id not in done]
    allowance = (p.daily_budget or 0) // CALLS_PER_TURN
    if limit is not None:
        allowance = min(allowance, limit)
    return todo[:allowance], previous, allowance


async def record(provider: str, limit: int | None) -> dict[str, Any]:
    os.environ["READBACK_CASSETTES"] = "record"
    os.environ.setdefault("READBACK_CASSETTE_DIR", str(ROOT / "evals" / "cassettes"))
    from readback_core import paths
    from readback_evals.runner import run_golden

    questions, previous, allowance = plan(provider, limit)
    if not questions:
        return {"provider": provider, "asked": 0, "allowance": allowance, "note": "nothing left to grade"}
    doc = await run_golden(provider, questions)
    fresh = {r["id"]: r for r in doc["rows"]}
    rows = [r for r in (previous or {}).get("rows", []) if r["id"] not in fresh] + list(fresh.values())
    doc["rows"] = sorted(rows, key=lambda r: r["id"])
    path = paths.results_dir() / "evals" / "runs" / f"{provider}.json"
    path.write_text(json.dumps(doc, indent=1, sort_keys=True, default=str) + "\n", encoding="utf-8")
    graded = sum(1 for r in fresh.values() if r.get("graded"))
    return {
        "provider": provider,
        "asked": len(questions),
        "graded": graded,
        "allowance": allowance,
        "total_rows": len(rows),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Record one provider's next slice of the golden set.")
    parser.add_argument("--provider", required=True)
    parser.add_argument("--limit", type=int, default=None, help="ask at most this many questions")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(record(args.provider, args.limit)), indent=1))


if __name__ == "__main__":
    main()
