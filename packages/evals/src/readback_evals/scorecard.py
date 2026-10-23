"""The scorecard: per provider and family on the test split, the development split beside it for the
gap, intervals, provider differences with Benjamini-Hochberg, the gate's catches, the interior tests,
the red team, the live share and the cassette dates. Built from results/evals on disk; nothing here
calls a model or the warehouse except the interior test of retrieval depth, which re-runs the floor.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any

from readback_core import paths
from readback_core.answer import Answer, ShippedClaim
from readback_providers import registry as provider_registry

from readback_evals.golden import FAMILIES, Question, load
from readback_evals.graders import grade
from readback_evals.stats import benjamini_hochberg, difference_interval, median, percentile, wilson

PROVIDER_ORDER = ("floor", "gemini", "groq", "openrouter", "sambanova", "ollama")
FLOOR_NOTE = (
    "The floor and the golden truth read one measures table, so the floor's row is the ceiling for the "
    "families it was written for, not a fair competitor; a model is listed as beating the floor only "
    "when its interval clears the floor's."
)


def _runs() -> dict[str, dict[str, Any]]:
    folder = paths.results_dir() / "evals" / "runs"
    out = {}
    for name in PROVIDER_ORDER:
        path = folder / f"{name}.json"
        if path.exists():
            out[name] = json.loads(path.read_text(encoding="utf-8"))
    return out


def _redteam(provider: str) -> dict[str, Any] | None:
    path = paths.results_dir() / "evals" / "redteam" / f"{provider}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def row_stats(rows: list[dict[str, Any]], total: int) -> dict[str, Any]:
    graded = [r for r in rows if r.get("graded")]
    n = len(graded)
    k = sum(1 for r in graded if r["passed"])
    low, high = wilson(k, n)
    shipped = [r for r in graded if r.get("verdict") != "refused"]
    claims = [c for r in shipped for c in r.get("claims", [])]
    agree = sum(1 for c in claims if c["verdict"] == "agree")
    tokens = sum(r["gate"]["tokens"] for r in graded)
    before = sum(r["gate"]["unsupported_before"] for r in graded)
    after = sum(r["gate"]["unsupported_after"] for r in shipped)
    refusal = [r for r in graded if r["family"] == "refusal"]
    return {
        "graded": n,
        "total": total,
        "live_share": n / total if total else 0.0,
        "passed": k,
        "accuracy": k / n if n else None,
        "low": low if n else None,
        "high": high if n else None,
        "readback_rate": agree / len(claims) if claims else None,
        "claims": len(claims),
        "unsupported_before": before,
        "unsupported_after": after,
        "unsupported_rate_before": before / tokens if tokens else 0.0,
        "unsupported_rate_after": after / tokens if tokens else 0.0,
        "repair_rate": sum(1 for r in graded if r.get("verdict") == "repaired") / n if n else None,
        "refusal_accuracy": sum(1 for r in refusal if r["passed"]) / len(refusal) if refusal else None,
        "median_tool_calls": median([r["tool_calls"] for r in graded]),
        "median_tokens": median([r["tokens_in"] + r["tokens_out"] for r in graded]),
        "p50_ms": percentile([r["latency_ms"] for r in graded], 0.5),
        "p99_ms": percentile([r["latency_ms"] for r in graded], 0.99),
        "models": sorted({r.get("model", "") for r in graded}),
    }


def by_family(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for fam in FAMILIES:
        f = [r for r in rows if r["family"] == fam and r.get("graded")]
        k = sum(1 for r in f if r["passed"])
        low, high = wilson(k, len(f))
        out[fam] = {"n": len(f), "passed": k, "accuracy": k / len(f) if f else None, "low": low, "high": high}
    return out


def _answer_from(row: dict[str, Any]) -> Answer:
    return Answer(
        question="",
        family=row["family"],
        text=row.get("text", ""),
        verdict=row.get("verdict", "refused"),
        provider="",
        model="",
        selection=row.get("selection") or [],
        direction=row.get("direction"),
        tools_called=row.get("tools_called", []),
        claims=[
            ShippedClaim(value=c["value"], unit=c["unit"], display=c["display"], verdict=c["verdict"])
            for c in row.get("claims", [])
        ],
    )


def tolerance_interior(
    rows: list[dict[str, Any]], golden: dict[str, Question], scales: Iterable[float] = (0.5, 1.0, 2.0)
) -> dict[str, float | None]:
    """Accuracy with the golden tolerance at a quarter, a half and one unit of the published rounding."""
    out: dict[str, float | None] = {}
    graded = [r for r in rows if r.get("graded")]
    for scale in scales:
        k = 0
        for r in graded:
            q = golden[r["id"]]
            scaled = q.model_copy(
                update={"claims": [c.model_copy(update={"tolerance": c.tolerance * scale}) for c in q.claims]}
            )
            k += grade(scaled, _answer_from(r)).passed
        out[f"{scale / 2:g} unit"] = k / len(graded) if graded else None
    return out


def ceiling_interior(
    rows: list[dict[str, Any]], ceilings: Iterable[int] = (4, 8, 12)
) -> dict[str, float | None]:
    """Accuracy had the tool call ceiling been 4, 8 or 12.

    An answer over the ceiling would have been refused.
    """
    graded = [r for r in rows if r.get("graded")]
    out: dict[str, float | None] = {}
    for c in ceilings:
        k = sum(1 for r in graded if r["passed"] and r.get("warehouse_calls", 0) <= c)
        out[str(c)] = k / len(graded) if graded else None
    return out


def split_size_interior(
    runs: dict[str, dict[str, Any]], golden: list[Question], sizes: Iterable[int] = (30, 50, 70)
) -> dict[str, str]:
    """The default provider chosen on development splits of 30, 50 and 70, drawn the same way."""
    from scripts.build_golden import split as draw

    out = {}
    for size in sizes:
        qs = [q.model_dump() for q in golden]
        for q in qs:
            q.pop("split")
        draw(qs) if size == 50 else _draw_sized(qs, size)
        dev = {q["id"] for q in qs if q["split"] == "dev"}
        out[str(size)] = choose_default(runs, dev)[0]
    return out


def _draw_sized(qs: list[dict[str, Any]], size: int) -> None:
    import random
    from collections import defaultdict

    rng = random.Random(20261024 + size)
    strata: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for q in sorted(qs, key=lambda q: q["id"]):
        strata[
            (q["family"], q["warehouses"][0] if q["family"] not in {"multi", "refusal"} else q["family"])
        ].append(q)
    share = size / len(qs)
    for key in sorted(strata):
        items = list(strata[key])
        rng.shuffle(items)
        take = max(1, round(len(items) * share))
        dev = {q["id"] for q in items[:take]}
        for q in strata[key]:
            q["split"] = "dev" if q["id"] in dev else "test"


def choose_default(runs: dict[str, dict[str, Any]], dev_ids: set[str]) -> tuple[str, str]:
    """The provider with the best development accuracy whose interval clears the floor's; else the floor."""

    def acc(name: str) -> tuple[float, float, float, int]:
        rows = [r for r in runs[name]["rows"] if r["id"] in dev_ids and r.get("graded")]
        k = sum(1 for r in rows if r["passed"])
        lo, hi = wilson(k, len(rows))
        return (k / len(rows) if rows else 0.0, lo, hi, len(rows))

    if "floor" not in runs:
        return "floor", "no floor run on disk"
    floor = acc("floor")
    best, why = "floor", "no model run beats the floor on the development split"
    for name in runs:
        if name == "floor":
            continue
        a = acc(name)
        if a[3] >= max(1, len(dev_ids) // 2) and a[1] > floor[2] and a[0] > acc(best)[0]:
            best, why = name, f"{name}'s development interval clears the floor's"
    return best, why


def build() -> dict[str, Any]:
    golden_list = load(paths.evals_dir() / "golden")
    golden = {q.id: q for q in golden_list}
    runs = _runs()
    totals = {s: sum(1 for q in golden_list if q.split == s) for s in ("dev", "test")}
    providers = {p.name: p for p in provider_registry.load()}
    card: dict[str, Any] = {"floor_note": FLOOR_NOTE, "prompt_hash": None, "providers_not_run": []}
    for split in ("test", "dev"):
        rows_out = []
        for name in PROVIDER_ORDER:
            if name not in runs:
                continue
            rows = [r for r in runs[name]["rows"] if r["split"] == split]
            s = row_stats(rows, totals[split])
            s.update(
                provider=name,
                families=by_family(rows),
                cassette_dates=runs[name].get("cassette_dates", []),
                prompt_hash=runs[name].get("prompt_hash"),
                model=providers[name].model_id() if name in providers else "",
            )
            rows_out.append(s)
            card["prompt_hash"] = card["prompt_hash"] or runs[name].get("prompt_hash")
        card[split] = {"rows": rows_out}
    card["providers_not_run"] = [p for p in PROVIDER_ORDER if p not in runs]
    # Differences from the floor on the test split, with Benjamini-Hochberg across them.
    test_rows = {r["provider"]: r for r in card["test"]["rows"]}
    comparisons = []
    if "floor" in test_rows:
        f = test_rows["floor"]
        for name, r in test_rows.items():
            if name == "floor" or not r["graded"]:
                continue
            low, high, p = difference_interval(r["passed"], r["graded"], f["passed"], f["graded"])
            comparisons.append(
                {
                    "provider": name,
                    "against": "floor",
                    "difference": r["accuracy"] - f["accuracy"],
                    "low": low,
                    "high": high,
                    "p": p,
                }
            )
    rejected = benjamini_hochberg([c["p"] for c in comparisons]) if comparisons else []
    for c, rej in zip(comparisons, rejected, strict=True):
        c["significant_bh"] = rej
    card["comparisons"] = comparisons
    dev_ids = {q.id for q in golden_list if q.split == "dev"}
    default, why = choose_default(runs, dev_ids)
    card["default_provider"], card["default_reason"] = default, why
    # The gate's catches on the test split, draft beside what shipped.
    catches = []
    for name, run in runs.items():
        for r in run["rows"]:
            if r["split"] == "test" and r.get("graded") and r["gate"].get("caught"):
                catches.append(
                    {
                        "provider": name,
                        "id": r["id"],
                        "caught": r["gate"]["caught"],
                        "draft": r["gate"].get("first_draft"),
                        "shipped": r.get("text"),
                    }
                )
    card["catches"] = catches
    # The interior tests.
    interior: dict[str, Any] = {}
    for name, run in runs.items():
        test = [r for r in run["rows"] if r["split"] == "test"]
        interior[name] = {"tolerance": tolerance_interior(test, golden), "ceiling": ceiling_interior(test)}
    interior["split_size"] = split_size_interior(runs, golden_list)
    ranks = {}
    for key in ("tolerance", "ceiling"):
        orders = []
        for idx in range(3):
            scores = {n: list(interior[n][key].values())[idx] or 0 for n in runs}
            orders.append(tuple(sorted(scores, key=lambda n: -scores[n])))
        ranks[key] = "degenerate" if len(set(orders)) > 1 else "stable"
    ranks["split_size"] = "degenerate" if len(set(interior["split_size"].values())) > 1 else "stable"
    interior["ranking"] = ranks
    interior["not_measured"] = {
        "retrieval depth": "measured on the floor only (definition family), by scripts/interior_depth.py",
        "summarization threshold": (
            "the golden set has no multi turn question, so the threshold never fires in the eval"
        ),
        "daily budget": (
            "the floor has no budget; a model's live share at half, as set and double its budget "
            "is printed with its row"
        ),
    }
    card["interior"] = interior
    depth = paths.results_dir() / "evals" / "interior_depth.json"
    if depth.exists():
        card["interior"]["depth"] = json.loads(depth.read_text(encoding="utf-8"))
    # The red team.
    card["redteam"] = {name: _redteam(name) for name in PROVIDER_ORDER if _redteam(name)}
    card["judge"] = {
        "run": False,
        "reason": (
            "the clarity judge needs a model key; it runs only from cassettes in CI and within budget live"
        ),
    }
    return card


def write(card: dict[str, Any]) -> None:
    path = paths.results_dir() / "evals" / "scorecard.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(card, indent=1, sort_keys=True, default=str) + "\n", encoding="utf-8")
