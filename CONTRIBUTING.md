# Contributing

Thank you for looking. readback is a portfolio build, so the bar for a change is that it keeps the
one promise the project makes: every number it says has been read back to the warehouse.

AGENTS.md is the single source for setup, the tests, the gates and the files not to edit by hand.
Read it first. What follows is how a change goes in.

## Before you start

- Open an issue for anything bigger than a typo, saying what you want to change and why.
- If the change touches a tool, the gate, the graders or the golden set, say how you will show it
  still holds: a test, a golden question, or a red team case.

## While you work

- One module per commit, conventional commit subjects (`feat(gate): ...`, `fix(mcp): ...`).
- A number in a document goes through the manifest. Add the value in packages/evals/publish.py and
  write `{{ v('key') }}` in the template. The claim gate fails the build on a typed digit.
- A new model request needs a cassette. Record it with scripts/record_cassettes.py inside the
  provider's free budget; CI replays and never calls a model.
- A changed prompt changes the prompt registry hash, and the registration check fails until
  DECISIONS.md has a dated entry naming the new hash and the reason.
- A change of direction goes in DECISIONS.md, dated. If it reverses an earlier entry, say which.

## Before you open the pull request

```
uv run pytest
uv run ruff check . && uv run ruff format --check . && uv run mypy
make gates
uv run python scripts/check_published_numbers.py
cd web && npm run typecheck && npm run build:e2e && npx playwright test
```

The release-gate skill in .claude/skills lists the full set run before a tag.

## Licences

Code is Apache 2.0. The warehouses keep their own terms, restated in data/PROVENANCE.md; a change
that adds a source adds its terms there in the same pull request.
