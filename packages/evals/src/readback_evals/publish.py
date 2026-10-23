"""Assemble results/manifest.json: every number a document or the site prints, with its provenance.

Read from the results on disk (the lock, the catalog, the golden set, the runs, the scorecard, the
red team, the conformance summary, the deploy verification, the latency, the live check, the
quality report) and nothing else. The section 19 checklist is computed here from that evidence, so
a line is marked done only when its file says so.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import subprocess
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq
import yaml
from readback_core import paths
from readback_core.manifest import Manifest, ManifestBuilder, write

from readback_evals.golden import FAMILIES, load

ROOT = paths.root


def _json(rel: str) -> Any:
    path = paths.root() / rel
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def _git_commits() -> int:
    try:
        out = subprocess.run(["git", "rev-list", "--count", "HEAD"], cwd=paths.root(), capture_output=True, text=True, check=True)
        return int(out.stdout.strip())
    except (OSError, subprocess.CalledProcessError, ValueError):
        return 0


def _decisions() -> tuple[int, int, int]:
    text = (paths.root() / "DECISIONS.md").read_text(encoding="utf-8")
    entries = re.findall(r"^## (\d{4}-\d{2}-\d{2}): (.+)$", text, re.M)
    reversals = sum(1 for _, title in entries if "reversal" in title.lower() or "reverses" in title.lower())
    protocol = sum(1 for _, title in entries if "revision 2026-07-28" in title)
    return len(entries), reversals, protocol


def assemble() -> Manifest:
    today = dt.date.today().isoformat()
    b = ManifestBuilder(today)

    def v(key: str, value: Any, fmt: str, origin: str, population: str, source: str = "build") -> None:
        b.value(key, value, fmt, origin=origin, population=population, source=source)

    # the warehouses
    lock = _json("data/warehouses.lock.json")
    total_tables = 0
    rows = []
    for name in ("doorstep", "turnaround", "ledger"):
        w = lock["warehouses"][name]
        cat = yaml.safe_load((paths.catalog_dir() / f"{name}.yaml").read_text(encoding="utf-8"))
        n_rows = sum(t["rows"] for t in cat["tables"])
        mb = sum(t["bytes"] for t in w["tables"]) / 1e6
        v(f"data.{name}.tables", len(w["tables"]), "int", "data/warehouses.lock.json", f"{name} at {w['tag']}", f"warehouse:{name}")
        v(f"data.{name}.rows", n_rows, "int", "catalog", f"every table of {name}", f"warehouse:{name}")
        v(f"data.{name}.tag", w["tag"], "text", "data/warehouses.lock.json", name, f"warehouse:{name}")
        v(f"data.{name}.commit", w["commit"][:7], "text", "data/warehouses.lock.json", name, f"warehouse:{name}")
        v(f"data.{name}.megabytes", round(mb, 1), "float1", "data/warehouses.lock.json", name, f"warehouse:{name}")
        total_tables += len(w["tables"])
        rows.append([name, w["tag"], w["commit"][:7], len(w["tables"]), n_rows, round(mb, 1), cat["covers"]])
    v("data.tables", total_tables, "int", "data/warehouses.lock.json", "the three warehouses", "warehouses")
    files = sum(len(w["tables"]) + len(w["documents"]) for w in lock["warehouses"].values())
    v("data.files", files, "int", "data/warehouses.lock.json", "every file the lock names", "warehouses")
    b.table("data.warehouses", ["Warehouse", "Tag", "Commit", "Tables", "Rows", "MB", "Covers"],
            ["text", "text", "text", "int", "int", "float1", "text"], rows, origin="data/warehouses.lock.json", population="the three warehouses", source="warehouses")

    # the catalog and its quarantine
    quarantine = _json("catalog/quarantine.json")
    measure_cols = unit_cols = def_cols = all_cols = metrics = 0
    for name in ("doorstep", "turnaround", "ledger"):
        cat = yaml.safe_load((paths.catalog_dir() / f"{name}.yaml").read_text(encoding="utf-8"))
        metrics += len(cat["metrics"])
        for t in cat["tables"]:
            for c in t["columns"]:
                all_cols += 1
                if c["role"] == "measure":
                    measure_cols += 1
                    unit_cols += c["unit"] is not None
                    def_cols += c["definition"] is not None
    v("catalog.columns", all_cols, "int", "catalog", "every column of the three warehouses", "catalog")
    v("catalog.measure_columns", measure_cols, "int", "catalog", "every measure column", "catalog")
    v("catalog.with_unit", unit_cols, "int", "catalog", "measure columns with a unit", "catalog")
    v("catalog.with_definition", def_cols, "int", "catalog", "measure columns with a definition", "catalog")
    v("catalog.metrics", metrics, "int", "catalog", "the metric layers of the three builds", "catalog")
    mi = pq.read_table(paths.catalog_dir() / "manifest_index.parquet")
    v("catalog.manifest_values", mi.num_rows, "int", "catalog/manifest_index.parquet", "every value of the three manifests", "catalog")
    idx = pq.read_table(paths.catalog_dir() / "index.parquet")
    v("catalog.documents", idx.num_rows, "int", "catalog/index.parquet", "the documents of the lexical index", "catalog")
    v("catalog.quarantine", len(quarantine["rows"]), "int", "catalog/quarantine.json", "every quarantine row", "catalog")
    qrows = [[w, rule, n] for w, rules in sorted(quarantine["counts"].items()) for rule, n in sorted(rules.items())]
    b.table("catalog.quarantine", ["Warehouse", "Rule", "Rows"], ["text", "text", "int"], qrows, origin="catalog/quarantine.json",
            population="the catalog quarantine, by warehouse and rule", source="catalog")

    # the golden set
    golden = load(paths.evals_dir() / "golden")
    v("golden.questions", len(golden), "int", "evals/golden", "the golden set", "golden")
    v("golden.dev", sum(q.split == "dev" for q in golden), "int", "evals/golden", "the development split", "golden")
    v("golden.test", sum(q.split == "test" for q in golden), "int", "evals/golden", "the test split", "golden")
    fam_rows = []
    for fam in FAMILIES:
        qs = [q for q in golden if q.family == fam]
        fam_rows.append([fam.replace("_", " "), len(qs), sum(q.split == "dev" for q in qs), sum(q.split == "test" for q in qs)])
    b.table("golden.families", ["Family", "Questions", "Development", "Test"], ["text", "int", "int", "int"], fam_rows,
            origin="evals/golden", population="the golden set by family", source="golden")
    first = _json("results/golden_first_ten.json") or []
    v("golden.first_ten_agree", sum(1 for r in first if r["agrees"]), "int", "scripts/check_first_ten.py", "ten development answers", "golden")

    # the protocol
    conf = _json("results/conformance.json") or {}
    v("mcp.revision", conf.get("revision", "2026-07-28"), "text", "results/conformance.json", "the server", "build")
    v("mcp.tools", conf.get("tool_count", 0), "int", "results/conformance.json", "the server's tools", "build")
    v("mcp.output_schemas", conf.get("output_schemas", 0), "int", "results/conformance.json", "tools with an output schema", "build")
    v("mcp.conformance", "passed" if conf.get("passed") else "not passed", "text", "results/conformance.json", "the conformance run", "build")
    transports = conf.get("transports", {})
    v("mcp.transports", ", ".join(k.replace("_", " ") for k, ok in sorted(transports.items()) if ok) or "none", "text",
      "results/conformance.json", "transports that answered the same list", "build")
    v("mcp.unsupported_version_error", conf.get("unsupported_version_error", 0) or 0, "int", "results/conformance.json", "the version error code", "build")

    # the scorecard
    card = _json("results/evals/scorecard.json") or {}
    v("eval.default_provider", card.get("default_provider", "floor"), "text", "results/evals/scorecard.json", "the default provider rule", "floor")
    v("eval.default_reason", card.get("default_reason", ""), "text", "results/evals/scorecard.json", "the default provider rule", "floor")
    v("eval.prompt_hash", (card.get("prompt_hash") or "")[:12], "text", "prompts/registry.yaml", "the prompt registry", "build")
    reg = _json("evals/registration.json") or {}
    v("eval.plan_hash", reg.get("plan_hash", "")[:12], "text", "evals/registration.json", "the registered plan", "build")
    v("eval.providers_not_run", ", ".join(card.get("providers_not_run", [])) or "none", "text", "results/evals/scorecard.json", "providers with no run", "build")
    for split in ("test", "dev"):
        table_rows = []
        for r in card.get(split, {}).get("rows", []):
            p = r["provider"]
            if split == "test":
                for key, fmt in (("accuracy", "pct1"), ("low", "pct1"), ("high", "pct1"), ("readback_rate", "pct1"), ("live_share", "pct0"),
                                 ("median_tool_calls", "float1"), ("p50_ms", "float1"), ("p99_ms", "float1"), ("repair_rate", "pct1"),
                                 ("refusal_accuracy", "pct1")):
                    if r.get(key) is not None:
                        v(f"eval.{p}.{key}", r[key], fmt, "results/evals/scorecard.json", f"{p} on the test split", "floor" if p == "floor" else "cassettes")
                for key in ("graded", "passed", "claims", "unsupported_before", "unsupported_after"):
                    v(f"eval.{p}.{key}", r[key], "int", "results/evals/scorecard.json", f"{p} on the test split", "floor" if p == "floor" else "cassettes")
            else:
                v(f"eval.{p}.dev_accuracy", r["accuracy"] or 0, "pct1", "results/evals/scorecard.json", f"{p} on the development split", "floor" if p == "floor" else "cassettes")
                v(f"eval.{p}.dev_passed", r["passed"], "int", "results/evals/scorecard.json", f"{p} on the development split", "floor" if p == "floor" else "cassettes")
            table_rows.append([p, r.get("models", [""])[0] if r.get("models") else "", r["graded"], r["passed"], r["accuracy"] or 0, r["low"] or 0, r["high"] or 0,
                               r["readback_rate"] or 0, r["unsupported_before"], r["unsupported_after"], r["repair_rate"] or 0,
                               r["median_tool_calls"] or 0, r["median_tokens"] or 0, r["p50_ms"] or 0, r["live_share"]])
        b.table(f"eval.{split}", ["Provider", "Model", "Graded", "Passed", "Accuracy", "Low", "High", "Readback rate", "Unsupported, draft",
                                  "Unsupported, shipped", "Repair rate", "Median tool calls", "Median tokens", "p50 ms", "Graded share"],
                ["text", "text", "int", "int", "pct1", "pct1", "pct1", "pct1", "int", "int", "pct1", "float1", "int", "float1", "pct0"], table_rows,
                origin="results/evals/scorecard.json", population=f"the {split} split, one row per provider", source="floor")
    fam_table = []
    for r in card.get("test", {}).get("rows", []):
        for fam, s in r["families"].items():
            if s["n"]:
                fam_table.append([r["provider"], fam.replace("_", " "), s["n"], s["passed"], s["accuracy"], s["low"], s["high"]])
    b.table("eval.families", ["Provider", "Family", "Questions", "Passed", "Accuracy", "Low", "High"],
            ["text", "text", "int", "int", "pct1", "pct1", "pct1"], fam_table, origin="results/evals/scorecard.json",
            population="the test split by provider and family", source="floor")
    interior = card.get("interior", {})
    it_rows = []
    for name in ("floor", "gemini", "groq", "openrouter", "sambanova", "ollama"):
        if name in interior:
            for knob, vals in interior[name].items():
                for setting, acc in vals.items():
                    it_rows.append([name, knob, setting, acc if acc is not None else 0])
    if "depth" in interior:
        for k in ("3", "5", "8"):
            it_rows.append(["floor", "retrieval depth (definitions)", k, interior["depth"][k]])
    for size, chosen in interior.get("split_size", {}).items():
        it_rows.append(["all", "development split size", size, 1.0 if chosen == "floor" else 0.0])
    b.table("eval.interior", ["Provider", "Operating point", "Setting", "Test accuracy"], ["text", "text", "text", "pct1"], it_rows,
            origin="results/evals/scorecard.json", population="the interior tests", source="floor")
    v("eval.interior_ranking", ", ".join(f"{k} {s}" for k, s in sorted(interior.get("ranking", {}).items())), "text",
      "results/evals/scorecard.json", "the ranking at the first neighbour of each operating point", "floor")
    tol = interior.get("floor", {}).get("tolerance", {})
    if tol:
        v("eval.floor.tolerance_quarter", tol.get("0.25 unit") or 0, "pct1", "results/evals/scorecard.json", "the floor at a quarter unit", "floor")
        v("eval.floor.tolerance_half", tol.get("0.5 unit") or 0, "pct1", "results/evals/scorecard.json", "the floor at half a unit", "floor")
    v("eval.catches", len(card.get("catches", [])), "int", "results/evals/scorecard.json", "gate catches on the test split", "floor")
    rt_rows = []
    for name, rt in sorted(card.get("redteam", {}).items()):
        v(f"redteam.{name}.passed", rt["passed"], "int", "results/evals/redteam", f"{name} on the red team", "floor")
        v(f"redteam.{name}.graded", rt["graded"], "int", "results/evals/redteam", f"{name} on the red team", "floor")
        for c in rt["cases"]:
            rt_rows.append([name, c["id"], c["kind"].replace("_", " "), "pass" if c.get("passed") else "fail", c.get("verdict", "")])
    b.table("redteam.cases", ["Provider", "Case", "Kind", "Result", "Answer"], ["text"] * 5, rt_rows, origin="results/evals/redteam",
            population="the 15 injection cases", source="floor")

    # deploy, latency, live check
    probe = _json("results/hosting_probe.json") or {}
    ver = _json("results/deploy/verification.json") or {}
    v("deploy.host", probe.get("host", "vercel"), "text", "results/hosting_probe.json", "the hosting probe", "live")
    v("deploy.base_url", ver.get("base_url") or probe.get("url") or "https://readback-mcp.vercel.app", "text", "deploy/live-url.txt", "the live server", "live")
    v("deploy.status", "verified" if ver.get("passed") else "not yet verified", "text", "results/deploy/verification.json", "the separate client check", "live")
    v("deploy.client", ver.get("client", "not run"), "text", "results/deploy/verification.json", "the separate client", "live")
    v("deploy.checked_at", ver.get("checked_at", "not run"), "text", "results/deploy/verification.json", "the separate client", "live")
    v("deploy.readback", f"{ver.get('readback_display', '')} {ver.get('readback_verdict', '')}".strip() or "not run", "text",
      "results/deploy/verification.json", "the readback the separate client made", "live")
    lat = _json("results/latency.json") or {}
    v("latency.status", "measured" if lat else "not measured", "text", "results/latency.json", "the load test", "live")
    if lat:
        v("latency.cold_start_ms", lat["cold_start_ms"], "float1", "results/latency.json", "the first call after idle", "live")
        v("latency.chat_p50_ms", lat["chat"]["p50_ms"], "float1", "results/latency.json", "chat turns through the floor", "live")
        v("latency.chat_p99_ms", lat["chat"]["p99_ms"], "float1", "results/latency.json", "chat turns through the floor", "live")
        v("latency.tool_p50_ms", lat["run_sql"]["p50_ms"], "float1", "results/latency.json", "run_sql over streamable HTTP", "live")
        v("latency.idle_minutes", lat.get("idle_minutes_before_first", 0), "int", "results/latency.json", "the idle wait before the cold call", "live")
    live = _json("results/live_check.json") or {}
    v("live.status", live.get("status", "not run"), "text", "results/live_check.json", "the live check in a browser", "live")
    providers_probe = _json("results/providers.json") or {}
    reached = [k for k, x in providers_probe.items() if isinstance(x, dict) and x.get("reached")]
    v("providers.reached", ", ".join(reached) or "none", "text", "results/providers.json", "providers the probe reached with a key", "live")

    # the build
    entries, reversals, protocol = _decisions()
    v("build.commits", _git_commits(), "int", "git", "the repository", "build")
    v("build.decisions", entries, "int", "DECISIONS.md", "dated decisions", "build")
    v("build.reversals", reversals, "int", "DECISIONS.md", "decisions that reverse an earlier one", "build")
    v("build.protocol_decisions", protocol, "int", "DECISIONS.md", "decisions that name the revision", "build")
    quality = _json("results/quality.json") or {}
    v("quality.coverage", quality.get("coverage", 0) / 100 if quality.get("coverage") else 0, "pct1", "results/quality.json", "line coverage of packages", "build")
    v("quality.tests", quality.get("tests", 0), "int", "results/quality.json", "tests passed", "build")
    rederive = _json("results/rederive.json") or {}
    v("rederive.status", rederive.get("status", "not run"), "text", "results/rederive.json", "the rederive in a worktree", "build")
    b.table("checklist", ["Item", "Status", "Evidence"], ["int", "text", "text"], checklist(), origin="readback_evals.publish",
            population="the definition of done", source="build")
    m = b.build()
    write(m, paths.results_dir() / "manifest.json")
    return m


def checklist() -> list[list[Any]]:
    """The section 19 lines, each marked from the evidence on disk."""
    root = paths.root()
    exists = lambda rel: (root / rel).exists()  # noqa: E731
    conf = _json("results/conformance.json") or {}
    card = _json("results/evals/scorecard.json") or {}
    ver = _json("results/deploy/verification.json") or {}
    probe = _json("results/hosting_probe.json") or {}
    lat = _json("results/latency.json")
    live = _json("results/live_check.json") or {}
    quality = _json("results/quality.json") or {}
    rederive = _json("results/rederive.json") or {}
    skills = _json("results/skills.json") or {}
    entries, reversals, protocol = _decisions()
    notebooks = [root / "notebooks" / f"{n}.ipynb" for n in ("01_the_tolerance", "02_the_floor", "03_the_injection")]
    floor_rows = {r["provider"]: r for r in card.get("test", {}).get("rows", [])}
    model_rows = [r for r in card.get("test", {}).get("rows", []) if r["provider"] != "floor" and r["graded"]]
    rt = card.get("redteam", {}).get("floor") or {}
    web_built = exists("web/out/index.html")
    lock = _json("data/warehouses.lock.json") or {"warehouses": {}}
    locked = sum(len(w["tables"]) for w in lock["warehouses"].values())
    golden = load(root / "evals/golden")
    dev = sum(q.split == "dev" for q in golden)
    items: list[tuple[bool, str]] = [
        (exists("data/warehouses.lock.json") and exists("catalog/quarantine.json") and exists("data/PROVENANCE.md"),
         f"data/warehouses.lock.json pins {locked} tables by digest; catalog/quarantine.json publishes every rule; data/PROVENANCE.md restates the terms"),
        (len(golden) == 150 and exists("results/golden_first_ten.json"),
         f"evals/golden holds {len(golden)} questions split {dev} and {len(golden) - dev}; results/golden_first_ten.json has the hand checked ten"),
        (bool(conf.get("passed")), f"results/conformance.json: revision {conf.get('revision', '')}, discovery, {conf.get('output_schemas', 0)} tools with output schemas, every transport, trace context"),
        (exists("tests/warehouse/test_guard.py") and exists("tests/mcp/test_tools.py") and exists("tests/api/test_client_budget.py"),
         "tests/warehouse/test_guard.py, tests/mcp/test_tools.py (readback, lookup round trip), tests/api/test_client_budget.py"),
        ("floor" in floor_rows and floor_rows["floor"]["graded"] == len(golden) - dev, "providers/registry.yaml; tests/providers; the floor graded on both splits in results/evals/runs/floor.json"),
        (exists("evals/registration.json") and exists("tests/agent/test_graph.py"), "tests/agent/test_graph.py; evals/registration.json holds the plan and prompt hashes"),
        (bool(ver.get("passed")) and bool(probe.get("reached")), f"results/deploy/verification.json from {ver.get('client', 'no client yet')}"),
        (exists("tests/api/test_http.py") and exists("results/persistence.json"), "tests/api/test_http.py; scripts/check_persistence.py wrote results/persistence.json"),
        (any((root / "results/traces").glob("*.parquet")) and web_built, "results/traces/*.parquet; the /traces page renders the waterfall"),
        (bool(model_rows) and bool(card.get("judge", {}).get("run")), "needs a model graded on the test split and the clarity judge, which need a key"),
        (bool(card.get("default_provider")), f"the default is {card.get('default_provider', 'floor')}: {card.get('default_reason', '')}"),
        (exists("AGENTS.md") and exists("CLAUDE.md") and exists(".github/copilot-instructions.md") and exists(".mcp.json")
         and bool(skills.get("valid")) and exists("docs/SPEC.md") and exists("server.json") and exists("docs/connect.md"),
         "AGENTS.md, CLAUDE.md, .github/copilot-instructions.md, .mcp.json, three skills (results/skills.json), docs/SPEC.md, server.json, docs/connect.md"),
        (web_built and live.get("status") == "passed", "the desk on GitHub Pages, checked in a browser in results/live_check.json"),
        (web_built and live.get("status") == "passed", "traces, evals, catalog, connect, playbook and report pages, in results/live_check.json"),
        (bool(lat) and live.get("status") == "passed", "results/latency.json with the cold start; results/live_check.json"),
        (rederive.get("drift") == 0, f"results/rederive.json: {rederive.get('status', 'not run')}"),
        (entries >= 10 and reversals >= 2 and protocol >= 1 and all(n.exists() for n in notebooks),
         f"DECISIONS.md has {entries} dated entries, {reversals} reversals, {protocol} protocol decisions; notebooks 01 to 03"),
        (quality.get("coverage", 0) >= 80 and quality.get("mypy") == "clean" and quality.get("ruff") == "clean" and 40 <= _git_commits() <= 60
         and rederive.get("drift") == 0 and quality.get("tagged") is True,
         f"coverage {quality.get('coverage', 'not measured')}, mypy {quality.get('mypy', 'not run')}, ruff {quality.get('ruff', 'not run')}, commits {_git_commits()}"),
    ]
    del rt
    return [[i + 1, "done" if ok else "not done", evidence] for i, (ok, evidence) in enumerate(items)]
