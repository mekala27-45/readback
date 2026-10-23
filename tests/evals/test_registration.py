"""Pre-registration: the committed hashes match, and a changed prompt fails without a dated decision."""

from __future__ import annotations

import shutil
from pathlib import Path

from scripts import check_registration

ROOT = Path(__file__).resolve().parents[2]


def test_the_committed_plan_and_prompts_are_as_registered() -> None:
    assert check_registration.check(ROOT) == []


def copy(tmp_path: Path) -> Path:
    for rel in ("evals/plan.yaml", "evals/registration.json", "DECISIONS.md"):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / rel, tmp_path / rel)
    shutil.copytree(ROOT / "prompts", tmp_path / "prompts")
    return tmp_path


def test_a_changed_prompt_fails_the_gate_until_a_decision_names_it(tmp_path: Path) -> None:
    root = copy(tmp_path)
    system = root / "prompts/system/analyst.md"
    system.write_text(system.read_text() + "\nOne more rule.\n")
    problems = check_registration.check(root)
    assert len(problems) == 1 and "prompt_hash" in problems[0]
    new = check_registration.current(root)["prompt_hash"][:12]
    with (root / "DECISIONS.md").open("a") as f:
        f.write(f"\n## 2026-10-24: the system prompt gained a rule\n\nNew registry hash {new}.\n")
    assert check_registration.check(root) == []


def test_a_changed_plan_fails_the_gate(tmp_path: Path) -> None:
    root = copy(tmp_path)
    plan = root / "evals/plan.yaml"
    plan.write_text(plan.read_text().replace("development: 50", "development: 70"))
    assert any("plan_hash" in p for p in check_registration.check(root))
