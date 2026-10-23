"""What the site reads: web/public/data, written from the committed results, catalog and documents.

The site never computes a figure. It reads the manifest's formatted values, the scorecard, the
conformance summary, the catalog as the build wrote it, the connect source, the playbook documents
rendered to HTML, the briefing, the eval turns with their trace ids, and two parquet files the browser
queries with DuckDB-WASM: the trace spans and the manifest index. The recorded session is written by
scripts/record_session.py, which needs the API running, so it is not rebuilt here.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any

import yaml
from markdown_it import MarkdownIt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from readback_core.formats import format_value
from readback_core.statements import STATEMENT

OUT = ROOT / "web" / "public" / "data"
MD = MarkdownIt("commonmark", {"html": False}).enable("table")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write(name: str, payload: Any) -> None:
    path = OUT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=1, sort_keys=True, default=str) + "\n", encoding="utf-8")


def strip_front_matter(text: str) -> tuple[dict[str, Any], str]:
    if text.startswith("---\n"):
        head, _, body = text[4:].partition("\n---\n")
        return yaml.safe_load(head) or {}, body
    return {}, text


def site() -> None:
    manifest = read_json(ROOT / "results" / "manifest.json")
    values = {k: format_value(v["value"], v["fmt"]) for k, v in manifest["values"].items()}
    tables = {}
    for key, t in manifest["tables"].items():
        tables[key] = {
            "columns": t["columns"],
            "formats": t["formats"],
            "rows": [
                [format_value(c, f) for c, f in zip(row, t["formats"], strict=True)] for row in t["rows"]
            ],
        }
    write(
        "site.json", {"as_of": manifest["as_of"], "statement": STATEMENT, "values": values, "tables": tables}
    )


def evals() -> None:
    shutil.copy(ROOT / "results" / "evals" / "scorecard.json", OUT / "scorecard.json")
    shutil.copy(ROOT / "evals" / "registration.json", OUT / "registration.json")
    golden: dict[str, dict[str, Any]] = {}
    for path in sorted((ROOT / "evals" / "golden").glob("*.yaml")):
        for q in yaml.safe_load(path.read_text(encoding="utf-8"))["questions"]:
            golden[q["id"]] = q
    turns = []
    for run in sorted((ROOT / "results" / "evals" / "runs").glob("*.json")):
        data = read_json(run)
        for r in data["rows"]:
            turns.append(
                {
                    "provider": data["provider"],
                    "id": r["id"],
                    "question": golden.get(r["id"], {}).get("question", ""),
                    "family": r["family"],
                    "split": r["split"],
                    "verdict": r.get("verdict"),
                    "passed": r.get("passed"),
                    "trace_id": r.get("trace_id"),
                    "text": r.get("text", ""),
                    "claims": [
                        {k: c.get(k) for k in ("display", "verdict", "evidence", "unit", "value")}
                        for c in r.get("claims", [])
                    ],
                }
            )
    write("turns.json", {"turns": turns})
    traces = OUT / "traces"
    traces.mkdir(parents=True, exist_ok=True)
    for f in sorted((ROOT / "results" / "traces").glob("*.parquet")):
        shutil.copy(f, traces / f.name)


def catalog() -> None:
    lock = read_json(ROOT / "data" / "warehouses.lock.json")
    warehouses = []
    for name in ("doorstep", "turnaround", "ledger"):
        c = yaml.safe_load((ROOT / "catalog" / f"{name}.yaml").read_text(encoding="utf-8"))
        entry = lock["warehouses"][name]
        warehouses.append(
            {
                "name": name,
                "repository": c["repository"],
                "tag": c["tag"],
                "commit": c["commit"],
                "as_of": c.get("as_of"),
                "covers": c.get("covers"),
                "metrics": c.get("metrics", []),
                "files": len(entry.get("tables", [])) + len(entry.get("documents", [])),
                "tables": [
                    {
                        "name": t["name"],
                        "rows": t["rows"],
                        "grain": t["grain"],
                        "description": t["description"],
                        "columns": [
                            {
                                k: col.get(k)
                                for k in (
                                    "name",
                                    "type",
                                    "role",
                                    "unit",
                                    "definition",
                                    "citation",
                                    "manifest_keys",
                                )
                            }
                            for col in t["columns"]
                        ],
                    }
                    for t in c["tables"]
                ],
                "lock": [{"path": f["path"], "sha256": f["sha256"]} for f in entry.get("tables", [])],
            }
        )
    synonyms = yaml.safe_load((ROOT / "catalog" / "synonyms.yaml").read_text(encoding="utf-8"))
    quarantine = read_json(ROOT / "catalog" / "quarantine.json")
    write(
        "catalog.json",
        {
            "warehouses": warehouses,
            "synonyms": synonyms.get("synonyms", synonyms),
            "quarantine": {"counts": quarantine["counts"], "rows": quarantine["rows"]},
        },
    )
    shutil.copy(ROOT / "catalog" / "manifest_index.parquet", OUT / "manifest_index.parquet")


def connect() -> None:
    source = yaml.safe_load((ROOT / "docs" / "connect.yaml").read_text(encoding="utf-8"))
    write(
        "connect.json",
        {
            "source": source,
            "server": read_json(ROOT / "server.json"),
            "conformance": read_json(ROOT / "results" / "conformance.json"),
        },
    )


def playbook() -> None:
    skills = []
    for path in sorted((ROOT / ".claude" / "skills").glob("*/SKILL.md")):
        meta, body = strip_front_matter(path.read_text(encoding="utf-8"))
        skills.append(
            {
                "name": meta.get("name", path.parent.name),
                "description": meta.get("description", ""),
                "html": MD.render(body),
            }
        )
    decisions_text = (ROOT / "DECISIONS.md").read_text(encoding="utf-8")
    decisions = []
    for chunk in decisions_text.split("\n## ")[1:]:
        title, _, body = chunk.partition("\n")
        date, _, name = title.partition(": ")
        decisions.append({"date": date, "title": name, "html": MD.render(body)})
    write(
        "playbook.json",
        {
            "agents": MD.render((ROOT / "AGENTS.md").read_text(encoding="utf-8")),
            "skills": skills,
            "decisions": decisions,
        },
    )
    briefing = (ROOT / "report" / "briefing.md").read_text(encoding="utf-8")
    write("briefing.json", {"html": MD.render(briefing)})


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    site()
    evals()
    catalog()
    connect()
    playbook()
    print(f"site data written to {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
