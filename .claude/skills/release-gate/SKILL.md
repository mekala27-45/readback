---
name: release-gate
description: The checklist run before tagging a readback release, every command in order. Use before pushing a version tag.
license: Apache-2.0
---

# Before the tag

Run each command; stop at the first failure and fix it before going on.

1. `uv sync --frozen` and `uv run python scripts/fetch_warehouses.py --verify`
2. `uv run ruff check . && uv run ruff format --check .`
3. `uv run mypy`
4. `uv run pytest --cov` (coverage at or above 80 percent)
5. `make gates` (dashes, vocabulary, statement, identifier scan, palette in both modes)
6. `uv run python scripts/check_registration.py`
7. `uv run python scripts/conformance.py`
8. `uv run readback eval --provider floor`, `uv run readback redteam --provider floor`,
   `uv run readback scorecard`, `uv run readback manifest`
9. `uv run python scripts/check_published_numbers.py --write`, then without `--write`: no drift
10. `for d in .claude/skills/*/; do uv run agentskills validate "$d"; done`
11. `cd web && npm run build && npm run test:e2e`
12. `uv run python scripts/reset_and_rederive.py` in a clean worktree: results/rederive.json must
    report zero drift
13. The live check (`deploy\probe.ps1`, `deploy\verify.ps1`, the browser check) recorded in
    results/live_check.json
14. Commit, push main, wait for CI to pass, then push the tag `v0.1.0`
