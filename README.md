# readback

**Every number my agent says is read back to the warehouse before you see it.**

readback is an analyst agent over three of my own data builds, served as an MCP server at protocol
revision 2026-07-28 and graded against answers that were already known. You ask a question about
housing (doorstep), flights (turnaround) or a fictional bank (ledger); the agent finds the table,
writes the SQL, and before the answer leaves, a gate made of plain code re-runs every number it is
about to say. A number that does not read back is repaired once, then refused. The live site
answers with **floor** (no model run beats the floor on the development split).

**Status: 13 of the eighteen items in the definition of done are done.** Not done yet:
item 10, item 13, item 14, item 15, item 18. The
checklist below says what each is waiting on.

| | |
|---|---|
| The desk | https://mekala27-45.github.io/readback/ |
| The MCP endpoint | https://readback-mcp.vercel.app/mcp (verified) |
| Connect a host | https://mekala27-45.github.io/readback/connect/ |
| The scorecard | https://mekala27-45.github.io/readback/evals/ |

## What it does, in numbers

- **The warehouses.** 163 published tables from doorstep, turnaround and ledger,
  fetched at their pinned tags and checked file by file against SHA-256 digests in the lock. Nothing
  is recomputed; the builds are the record.
- **The catalog.** 1,105 measure columns, every one with a unit
  (1,105), 657 with a definition lifted from
  the build's own documents and cited to the line. The rest sit in a quarantine of
  2,129 named rows rather than getting a definition I made up.
- **The protocol.** 7 tools, each with an output schema; stateless; public hour
  long cache hints; discovery; trace context carried through the request metadata; conformance
  passed over in memory, stdio, streamable http.
- **The golden set.** 150 questions whose answers were known before the
  agent existed, split 50 development and 100 test.
- **The floor**, the planner with no model in it: **98.0%** on the test
  split (interval 93.0% to 99.4%), every one of its
  174 shipped numbers read back. It shares the measures table with the
  golden truth, so read its row as a ceiling for the families it was written for, not as a rival.
- **The red team.** 15 of 15 injection
  cases passed on the floor. The first run passed fewer, and DECISIONS.md says what it caught.
- **Models graded so far:** gemini, groq, openrouter, sambanova, ollama have not run yet. A provider's row
  appears when the live eval has recorded its cassettes; it never extrapolates from a partial run.

## How it works

```
  doorstep, turnaround, ledger at v0.1.0   (fetched by digest, read only)
        v  catalog: units, cited definitions, synonyms, a lexical index, the quarantine
        v  DuckDB, three read only schemas, the SQL guard in front
   MCP SERVER   warehouses  describe  search_catalog  run_sql  published  readback  lookup
        ^  the agent is a client of its own server (in memory in tests, HTTP in production)
   AGENT        classify  plan  act  gate  repair  refuse  interrupt  answer   (LangGraph)
        |  router: gemini, groq, openrouter, sambanova, ollama, the floor; a budget each
        v
   EVALUATION   golden set, graders in code, red team, cassettes   TRACING  one trace per turn
```

The agent calls the same seven tools any host gets, so a bug in a tool shows up in the eval and a
bug in the protocol shows up in the separate client. The gate is code, because a model checking a
model is a vote, and a vote is not a verification. The floor exists because a free tier can vanish
in a week, and a product that only works with a key is a demo. The known truth is the manifests,
because three builds spent a day each proving their numbers. ARCHITECTURE.md has the rest.

## The skills, and where each lives

| Skill | Where it lives |
|---|---|
| MCP server design | packages/mcp_server, docs/protocol.md, results/conformance.json |
| MCP client | packages/agent (the client), tests over the in memory transport |
| Agent orchestration | packages/agent: the LangGraph graph, interrupts, the checkpointer |
| Tool use and structured outputs | the Answer schema, the tool schemas, the output mode per provider |
| Natural language to SQL, verified | packages/planner, run_sql, the readback tool |
| Evaluation engineering | packages/evals, evals/golden, the scorecard |
| Known truth and graders in code | catalog/manifest_index.parquet, packages/evals graders |
| Red teaming and injection defense | evals/redteam, the gate, docs/security.md |
| Observability | packages/tracing, docs/observability.md, the /traces page |
| Cost control and model routing | providers/registry.yaml, the budget ledger, the cassettes |
| Resilience without a key | the floor, the recorded session on the site |
| Durable execution and human in the loop | the Postgres checkpointer, the interrupt on an ambiguous name |
| Context engineering | prompts/registry.yaml, search then describe, tokens per question |
| Semantic layer and data catalog | catalog/, the units, the synonym table, catalog/measures.yaml |
| Security | the SQL guard, the read only connection, redaction, the identifier scan, the client budget |
| APIs and persistence | packages/api, scripts/check_persistence.py |
| Serverless deployment | Dockerfile.vercel, the cold start measurement |
| Spec driven, agent assisted engineering | AGENTS.md, .claude/skills, docs/SPEC.md, .mcp.json, DECISIONS.md |
| Interoperability standards | server.json, the connect page |
| Frontend for agents | web/: the streaming desk, the chips, the trace viewer |
| Statistics for evaluation | Wilson intervals, Benjamini-Hochberg, kappa |
| Communication | report/briefing.md, the pushback paragraph on every page |
| Reproducibility | the claim gate, the rederive, the cassettes |

## The definition of done

| Item | Status | Evidence |
|---:|---|---|
| 1 | done | data/warehouses.lock.json pins 163 tables by digest; catalog/quarantine.json publishes every rule; data/PROVENANCE.md restates the terms |
| 2 | done | evals/golden holds 150 questions split 50 and 100; results/golden_first_ten.json has the hand checked ten |
| 3 | done | results/conformance.json: revision 2026-07-28, discovery, 7 tools with output schemas, every transport, trace context |
| 4 | done | tests/warehouse/test_guard.py, tests/mcp/test_tools.py (readback, lookup round trip), tests/api/test_client_budget.py |
| 5 | done | providers/registry.yaml; tests/providers; the floor graded on both splits in results/evals/runs/floor.json |
| 6 | done | tests/agent/test_graph.py; evals/registration.json holds the plan and prompt hashes |
| 7 | done | results/deploy/verification.json from AJAY, Windows, PowerShell 5.1.26100.9711, plain JSON-RPC |
| 8 | done | tests/api/test_http.py; scripts/check_persistence.py wrote results/persistence.json |
| 9 | done | results/traces/*.parquet; the /traces page renders the waterfall |
| 10 | not done | needs a model graded on the test split and the clarity judge, which need a key |
| 11 | done | the default is floor: no model run beats the floor on the development split |
| 12 | done | AGENTS.md, CLAUDE.md, .github/copilot-instructions.md, .mcp.json, three skills (results/skills.json), docs/SPEC.md, server.json, docs/connect.md |
| 13 | not done | the desk on GitHub Pages, checked in a browser in results/live_check.json |
| 14 | not done | traces, evals, catalog, connect, playbook and report pages, in results/live_check.json |
| 15 | not done | results/latency.json with the cold start; results/live_check.json |
| 16 | done | results/rederive.json: no drift |
| 17 | done | DECISIONS.md has 29 dated entries, 2 reversals, 5 protocol decisions; notebooks 01 to 03 |
| 18 | not done | coverage 85.4, mypy clean, ruff clean, commits 33, rederive no drift |

## Run it

```
uv sync
uv run python scripts/fetch_warehouses.py
uv run readback-mcp                      # the server over stdio
uv run uvicorn readback_api.main:app     # the API and /mcp over HTTP
uv run readback eval --provider floor    # the golden set through the floor
```

No key is needed. AGENTS.md has the tests and the gates.

## What the platform engineer would push back on

The known answers are this portfolio's own published numbers, so the eval measures whether the agent
reads them correctly, not whether they are right; each build proved its own. The gate checks that a
number agrees with the query it cites, not that the query was the right one, which the graders check
separately. The live eval runs on free quotas, so a model's row covers the share of the test split
its budget allowed, and says so. The floor only answers the families it was written for, and refuses
the rest.

## How this was built

I wrote the specification and made the calls; an AI pair (Claude) wrote much of the code with me, and
the commits carry its co-author trailer. Every number above comes from a query or a test the
repository runs, and the claim gate fails the build if this file says anything else.

> Answers are drawn from the published tables of three portfolio builds by Ajay Mekala: doorstep (public housing data from FHFA, the Census Bureau, HUD, the CFPB and Freddie Mac), turnaround (public flight data from the Bureau of Transportation Statistics, the FAA and OurAirports, with weather from Open-Meteo under CC BY 4.0) and ledger (a fictional bank, Harborline, with public HMDA, CFPB, FDIC and macro series). No person appears in any table, and questions are redacted before a model sees them. Every number is read back to the warehouse before it is shown. This is a portfolio demonstration, not financial, travel or lending advice.
