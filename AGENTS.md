# AGENTS.md

How to work in this repository, for a person or a coding agent. This file is the single source;
CLAUDE.md and .github/copilot-instructions.md only point here.

## What this is

readback is an analyst agent over three published warehouses (doorstep, turnaround, ledger),
served as an MCP server at protocol revision 2026-07-28, where every number the agent says is read
back to the warehouse before it is shown. docs/SPEC.md is the specification the build was run from;
deviations from it are in DECISIONS.md.

## Set up

```
uv sync                                  # Python 3.12, the twelve workspace packages
uv run python scripts/fetch_warehouses.py   # the 177 files the lock names, checked by digest
uv run python scripts/build_catalog.py      # only when the lock, the rules or the overrides change
cd web && npm ci                          # only for the site
```

The warehouses are fetched, never committed. Nothing needs a key: without one, the floor answers.

## Run the tests and the gates

```
uv run pytest                       # the suite; replays cassettes, never calls a provider
uv run ruff check . && uv run mypy  # lint and types, strict
make gates                          # dashes, vocabulary, statement, identifier scan, palette
uv run python scripts/check_published_numbers.py   # the claim gate: documents match the manifest
uv run python scripts/check_registration.py        # the plan and prompts as registered
uv run python scripts/conformance.py               # the protocol, over three transports
```

What each gate refuses:

- **Dashes.** An em dash or an en dash in any authored file.
- **Vocabulary.** The filler words in scripts/check_vocabulary.py.
- **Statement.** A document or a built page without the statement in readback_core.statements.
- **Identifier scan.** A card number, an email, a phone number in the answer log or the traces,
  or a token from data/planted_identifiers.txt, anywhere published.
- **Palette.** A slot of web/src/theme/palette.json that fails contrast or separation.
- **Claim gate.** A document that differs from its template rendered against results/manifest.json,
  or a digit typed into a template outside an expression.
- **Registration.** A changed eval plan or prompt without a dated DECISIONS.md entry naming its hash.
- **The readback gate**, at run time: an answer with a number that has no claim, or a claim that
  does not read back.

## Rules

- Every number in a document is rendered from the manifest. Write `{{ v('key') }}` in a template,
  never the number. Answers from the agent never enter a document.
- Every number the agent says has a claim with evidence and an agreeing readback. Never add an
  exemption to readback_gate.gate without a test for it and a DECISIONS.md entry.
- The SQL guard and the read only connection are two lines of defense; do not relax either.
- CI never calls a model. A new model request needs a cassette, recorded by
  scripts/record_cassettes.py within the provider's budget.
- A decision goes in DECISIONS.md, dated, with the reason; a decision that reverses one says so,
  and one that chooses a protocol path names the revision.

## Files an agent must not edit by hand

- data/warehouses.lock.json (written by scripts/lock_warehouses.py)
- catalog/*.yaml, catalog/*.parquet, catalog/quarantine.json (written by scripts/build_catalog.py;
  change catalog/unit_rules.yaml, definition_terms.yaml or overrides.yaml instead)
- evals/golden/*.yaml (written by scripts/build_golden.py; see the golden-question skill)
- evals/cassettes/ (written only by the recorder)
- evals/registration.json (written once)
- results/manifest.json and every rendered document (README.md, RESULTS.md, report/)

## Commits

Conventional commits, one module at a time: `feat(mcp): ...`, `fix(gate): ...`, `test(api): ...`,
`docs(agents): ...`, `ci: ...`, `chore: ...`. The subject says what changed; the body says why.

## Skills

.claude/skills holds three, in the Agent Skills format: warehouse-question (answer a question
through the tools with the readback rule), golden-question (add a golden question with its known
truth), release-gate (every command before a tag).

> Answers are drawn from the published tables of three portfolio builds by Ajay Mekala: doorstep (public housing data from FHFA, the Census Bureau, HUD, the CFPB and Freddie Mac), turnaround (public flight data from the Bureau of Transportation Statistics, the FAA and OurAirports, with weather from Open-Meteo under CC BY 4.0) and ledger (a fictional bank, Harborline, with public HMDA, CFPB, FDIC and macro series). No person appears in any table, and questions are redacted before a model sees them. Every number is read back to the warehouse before it is shown. This is a portfolio demonstration, not financial, travel or lending advice.
