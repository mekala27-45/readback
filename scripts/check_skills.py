"""Validate the three skills with the Agent Skills reference validator; results/skills.json."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from skills_ref import validate

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {"warehouse-question", "golden-question", "release-gate"}


def check() -> dict[str, object]:
    rows = []
    for folder in sorted((ROOT / ".claude/skills").iterdir()):
        if not folder.is_dir():
            continue
        errors = validate(folder)
        lines = len((folder / "SKILL.md").read_text(encoding="utf-8").splitlines())
        rows.append({"skill": folder.name, "errors": errors, "lines": lines, "under_500": lines < 500})
    names = {r["skill"] for r in rows}
    valid = names == EXPECTED and all(not r["errors"] and r["under_500"] for r in rows)
    return {"skills": rows, "valid": valid}


if __name__ == "__main__":
    out = check()
    (ROOT / "results" / "skills.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=1))
    sys.exit(0 if out["valid"] else 1)
