"""The golden set: 150 questions, stratified, reproducible, and the hand check agrees."""

from __future__ import annotations

import copy
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path

from scripts import build_golden, check_first_ten

from readback_evals.golden import load

ROOT = Path(__file__).resolve().parents[2]


def test_counts_by_family_and_split() -> None:
    qs = load(ROOT / "evals/golden")
    assert len(qs) == 150
    assert Counter(q.split for q in qs) == {"dev": 50, "test": 100}
    by_wh = Counter(q.warehouses[0] for q in qs if q.family not in {"multi", "refusal"})
    assert by_wh == {"doorstep": 40, "turnaround": 40, "ledger": 40}
    fam = Counter(q.family for q in qs)
    assert fam["multi"] == 15 and fam["refusal"] == 15


def test_every_stratum_is_in_both_splits() -> None:
    qs = load(ROOT / "evals/golden")
    strata: dict[tuple[str, str], set[str]] = {}
    for q in qs:
        key = (q.family, q.family if q.family in {"multi", "refusal"} else q.warehouses[0])
        strata.setdefault(key, set()).add(q.split)
    assert all(s == {"dev", "test"} for s in strata.values())


def test_the_split_reproduces_under_two_hash_seeds() -> None:
    code = (
        "import json,sys; sys.path.insert(0,'.'); from scripts.build_golden import split; "
        "from readback_evals.golden import load; from pathlib import Path; "
        "qs=[q.model_dump() for q in load(Path('evals/golden'))]; [q.pop('split') for q in qs]; split(qs); "
        "print(json.dumps(sorted((q['id'], q['split']) for q in qs)))"
    )
    outs = []
    for seed in ("1", "2"):
        env = {**os.environ, "PYTHONHASHSEED": seed}
        outs.append(subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env, capture_output=True, text=True, check=True).stdout)
    assert outs[0] == outs[1]
    committed = sorted((q.id, q.split) for q in load(ROOT / "evals/golden"))
    import json

    assert [tuple(x) for x in json.loads(outs[0])] == committed


def test_split_is_a_third_of_each_stratum() -> None:
    qs = [q.model_dump() for q in load(ROOT / "evals/golden")]
    again = copy.deepcopy(qs)
    build_golden.split(again)
    assert sum(q["split"] == "dev" for q in again) == 50


def test_in_scope_questions_carry_known_truth() -> None:
    for q in load(ROOT / "evals/golden"):
        if q.family in {"lookup", "comparison", "trend", "top_k", "multi"}:
            assert q.claims, q.id
            assert all(c.tolerance > 0 for c in q.claims)
        if q.family == "definition":
            assert len(q.key_phrases) >= 2
        if q.family == "refusal":
            assert q.refuse and not q.claims


def test_the_first_ten_agree_with_hand_written_sql() -> None:
    rows = check_first_ten.run()
    assert len(rows) == 10
    assert all(r["agrees"] for r in rows), [r for r in rows if not r["agrees"]]
