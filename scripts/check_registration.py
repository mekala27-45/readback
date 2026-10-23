"""The pre-registration gate: the plan and the prompt registry as registered, or a dated decision.

python scripts/check_registration.py             # check
python scripts/check_registration.py --register  # write evals/registration.json (once, before live calls)
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from readback_agent.prompts import build as build_registry
from readback_core.hashing import sha256_text

REGISTRATION = ROOT / "evals" / "registration.json"


def plan_hash(root: Path = ROOT) -> str:
    return sha256_text((root / "evals" / "plan.yaml").read_text(encoding="utf-8"))


def current(root: Path = ROOT) -> dict[str, str]:
    return {"plan_hash": plan_hash(root), "prompt_hash": build_registry(root).digest}


def check(root: Path = ROOT) -> list[str]:
    registered = json.loads((root / "evals" / "registration.json").read_text(encoding="utf-8"))
    now = current(root)
    decisions = (root / "DECISIONS.md").read_text(encoding="utf-8")
    problems = []
    for key in ("plan_hash", "prompt_hash"):
        if now[key] != registered[key] and now[key][:12] not in decisions:
            problems.append(
                f"{key} is {now[key][:12]}, registered {registered[key][:12]}, "
                f"and DECISIONS.md has no dated entry naming {now[key][:12]}"
            )
    return problems


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--register", action="store_true")
    args = parser.parse_args()
    if args.register:
        if REGISTRATION.exists():
            print("already registered; a change needs a dated entry in DECISIONS.md, not a new registration")
            return 1
        REGISTRATION.write_text(
            json.dumps(
                {
                    **current(),
                    "registered_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
                    "before_first_live_call": True,
                },
                indent=1,
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"registered plan {current()['plan_hash'][:12]} and prompts {current()['prompt_hash'][:12]}")
        return 0
    problems = check()
    if problems:
        print("registration gate failed:\n" + "\n".join(problems))
        return 1
    print(
        "registration gate: the plan and the prompt registry are as registered, "
        "or a dated decision names the change"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
