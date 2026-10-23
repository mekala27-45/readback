# Architecture

readback is one Python workspace and one static site. The workspace holds an MCP server over three
read only warehouses, an agent that is a client of that server, a gate that re-runs every number the
agent is about to say, and the evaluation that grades all of it against answers known in advance.
The site is a desk for asking questions, and pages for the traces, the scorecard and the catalog.

```
  doorstep, turnaround, ledger at their pinned tags    (fetched, checked by SHA-256, read only)
        |
        v  catalog/        units, cited definitions, synonyms, a lexical index, the quarantine
        v  warehouse       DuckDB: a file of views over the parquet, opened read only, the SQL guard in front
        |
   MCP SERVER   warehouses  describe  search_catalog  run_sql  published  readback  lookup
        ^            stdio for a local host, streamable HTTP at /mcp for everything else
        |
   AGENT        classify, plan, act, gate, repair, refuse, interrupt, answer      (LangGraph)
        |       router over the providers and the floor, a daily budget each, cassettes
        v
   API          /v1/chat as server sent events, the answer log, the spans      (FastAPI, Postgres)
        |
   SITE         the desk, traces, scorecard, catalog, connect, playbook, briefing  (GitHub Pages)
```

## Why the agent is a client of its own server

The agent never touches DuckDB. It lists the same seven tools any host gets, calls them over the
same protocol, and reads the same structured results. In tests the transport is in memory; in
production it is streamable HTTP on loopback. The point is that there is no private path: a bug in a
tool shows up in the eval, because the eval drives the agent through the tools, and a bug in the
protocol shows up in the separate client that verifies the deployment, because that client was not
written against the agent's code. Neither can hide behind a shortcut the other does not take.

## Why the gate is code and not a second model

A model checking a model is a vote, and a vote is not a verification. The gate extracts every number
token from the draft, sets aside the ones that are years, identifiers, ordinals or list counts, and
sends each remaining claim to the readback tool with its source: a sealed result handle, a manifest
key, a catalog fact or a cited definition. The tool re-runs the query or reads the published value,
converts units the one way the catalog allows, and compares within half the step of the rounding
the claim was shown at. A number that does not agree is repaired once, by asking the model again with
the disagreement in hand, and then refused. The gate never asks anyone whether a number is right.

The handles matter. A run_sql result comes back with a handle that seals the SQL, the digest of the
rows and the trace id of the turn with an HMAC. The model sees short aliases (r1, r2) in place of the
handles, so it cannot forge one, and a handle from another turn does not open in this one.

## Why the floor exists

The free tier of a provider can disappear in a week, and a product that only works with a key is a
demo. The floor is a planner with no model in it: rules that classify the question, the measures
table that maps a measure to its SQL, and sentence templates that draft from the rows. It answers
the families it was written for and refuses the rest. It goes through the same gate as a model, and
it is the provider the router falls back to when every budget is spent or every key is missing.

The floor reads the same measures table the golden truth was built from, so its scorecard row is a
ceiling for those families, not a fair competitor. A model is called better only when its interval
clears the floor's.

## Why the known truth is the manifests

Three builds spent a day each proving their numbers, and each published a manifest of the values its
documents state. This build reads those values and does not pretend to know better. The golden set
takes its answers from the manifests and from SQL over the same tables, written before the agent
existed; the first ten were run by hand against the real tables before anything else was built on
them.

## The packages, and the one direction of import

```
core        the answer model, units, formats, the manifest, paths, the statement
render      the claim gate: every document is a template over results/manifest.json
catalog     building the catalog, the lexical index, synonyms, definitions, measures
warehouse   the read only connection, the SQL guard, execution with a timeout
gate        token extraction, exemptions, comparison
tracing     OpenTelemetry setup, the Parquet exporter, span helpers
mcp_server  the server, its tools, resources and prompts
providers   the registry, the router, the budget ledger, cassettes, model construction
planner     the floor: classification and the deterministic plans
agent       the graph, the tool client, redaction, the prompt registry
evals       golden set, graders, statistics, red team, scorecard, publishing the manifest
api         the ASGI app: /mcp, /v1/chat, the answer log, the client budget
```

Each package imports only from packages above it in this list, with two exceptions that are
deliberate: the agent imports the server only to run it in memory in tests, and nothing imports the
api.

## State and where it lives

The warehouses are files, fetched and never written. The catalog is committed YAML and parquet,
regenerated by a script and checked in CI. The answer log, the spans, the budget ledger and the
client budget live in Postgres on Neon in production and in SQLite on a laptop, behind one SQLAlchemy
layer with an Alembic migration. The budget row and the audit row are written in the same
transaction, so a turn is either counted and logged or neither. The LangGraph checkpointer uses the
same Postgres, which is what lets a turn interrupted for a choice, or killed between act and gate,
resume on another instance.

## What runs where

```
laptop or CI    everything, with SQLite and the floor; cassettes replay model calls
Vercel Hobby    the API and /mcp in a container function (Dockerfile.vercel), Neon for state
GitHub Pages    the static site, reading committed results and calling the API when it is awake
GitHub Actions  tests and gates, the site, a scheduled live eval inside each provider's free budget
```

Nothing here needs a card. When a host or a key is missing, the floor answers and the desk replays
a recorded session, and both say so.
