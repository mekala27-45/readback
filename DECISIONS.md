# Decisions

Dated, newest last. A decision that reversed an earlier one says so and names it. Every decision
that chose a protocol path cites the revision, 2026-07-28, and the reason.

## 2026-10-23: one uv workspace, twelve packages, one direction of import

core, render, catalog, warehouse, gate, tracing, mcp_server, providers, planner, agent, evals and
api. The agent imports the server only to run it in memory in tests; in production it reaches the
server over streamable HTTP like any other host. Nothing imports the api.

## 2026-10-23: the warehouses are fetched, never vendored

The 177 files the lock names come to 85 MB. They are fetched from each repository at its tag and
checked against the lock, in CI, in the container build and on a laptop, rather than committed here.
A copy committed here could drift from the build it claims to be; a fetch checked against a digest
cannot. The cost is one network step before anything runs, which the fetch keeps idempotent.

## 2026-10-23: the marts take their units from a committed rule table

The data dictionaries of doorstep and turnaround cover their CSV bundles and say nothing about the
marts. The units of mart columns come from catalog/unit_rules.yaml, matched by column name, first
match wins, with a table pattern where a name means two things. This is a hand edit and it is the
largest one in the build.

The first build ran the range check on every column the rules called a fraction and caught 27
columns whose values could not be a fraction: the denominators of a share (renters_with_share,
owners_mortgage_with_share), counts named under_35 and over_2x in doorstep's borrower mart, rates
per hundred residents in chapters 4 and 7, ledger's deposit rates stored in percent, and the
allowance coverage, which is a multiple. Each got a rule; the second build had none. The check stays
in the build, so a new column that lies about its unit lands in the quarantine.

## 2026-10-23: definitions are lifted, and a hand edit is labeled as one

A column's definition comes, in order, from ledger's metrics/bank.yaml, from an entry in the
build's docs/definitions.md through the hand table catalog/definition_terms.yaml (the text itself is
lifted verbatim and cited by file and line), or from catalog/overrides.yaml, where each sentence is
mine and marked as a hand edit. 448 measure columns are covered by none of these and sit in the
quarantine as "column lacks a definition"; they can still be queried, and describe says the
definition is missing rather than inventing one.

## 2026-10-23: a manifest key has no table behind it in any of the three builds

The three manifests record the step that produced a value (its origin and population), not the
table and SQL. 1,680 numeric keys are quarantined under that rule. The readback compares a claim
with the published value itself, so the rule costs the reader a link, not a check.

## 2026-10-23: the semantic layer is a measures table both the floor and the golden set read

catalog/measures.yaml lists 27 measures (a phrase, a table, an entity, a time and the aggregate SQL).
The golden set computes its known answers from it and the floor answers from it, so a question
about a listed measure has one SQL for truth and for the floor. A model writes its own SQL and the
graders only ask whether its numbers agree. Ten development answers were then recomputed by SQL
written by hand from other tables (scripts/check_first_ten.py), and all ten agreed.

## 2026-10-23: ledger's generated identifiers stay, and questions about them are refused

ledger's queue and retention tables carry customer, account and loan identifiers. They belong to
the generated records of a fictional bank, so the warehouse holds no person. The server does not
drop them, because they are what those tables are; the agent refuses any question about one
identified customer, account or loan, and the refusal set tests it.

## 2026-10-23: the server is stateless, and a result handle carries its own statement (revision 2026-07-28)

The revision removed the session, so nothing the server mints may depend on memory between calls.
run_sql returns a result_id that is the normalized statement, the digest of its rows and the trace
id of the caller's request chain, encoded and sealed with an HMAC. readback opens the handle,
re-runs the statement, and refuses it if the rows changed, the seal does not match, or the trace id
belongs to another chain. Nothing is stored. The key comes from READBACK_RESULT_KEY or, when that is
unset, from the digest of the lock file, which makes the seal an integrity check and not a secret:
forging one buys only a read only query the caller could have run anyway.

## 2026-10-23: lookup uses the multi round trip pattern, with a fallback (revision 2026-07-28)

The SDK at 2.3 exposes the revision's input required result. When a name matches more than one
entity (Portland, Springfield, Columbus) and the client declared the elicitation capability, lookup
returns an input required result carrying one elicitation whose schema is an enum of the
candidates; the client retries with the choice and the echoed request state. A client that did not
declare elicitation gets the candidates as structured content with needs_choice set, and the
agent asks the person through a graph interrupt. Both paths are tested.

## 2026-10-23: cache hints are public and an hour on every list and read (revision 2026-07-28)

tools/list, prompts/list, resources/list, resources/templates/list, resources/read and
server/discover carry ttlMs 3600000 and cacheScope public. The catalog and the published values
change only with a deploy, and none of these results depends on who asked.

## 2026-10-23: nothing deprecated is implemented (revision 2026-07-28)

No roots, no sampling, no logging feature, and no subscriptions/listen (the server has nothing that
changes). The capabilities test asserts logging is absent.

## 2026-10-23: the catalog's dollar rule claimed price to income, and the readback caught it

The first readback through the server returned price_to_income in dollars: the dollar rule's
.*_income pattern matched it before the ratio rule did. A ratio rule for income ratios now runs
first, and purchase_with_income moved to the counts. Recorded as the second fix to the unit rules.

## 2026-10-23: the floor and the golden set share one measures table, and the scorecard says so

The floor answers from catalog/measures.yaml and the golden truth is computed from the same file, so
the floor's row is a ceiling for the families it was written for, not a fair competitor: it scored
50 of 50 on the development split the first time it ran. Its job is to be the answer when no key is
present and the bar a model must clear, and the scorecard prints that sentence beside its row. A
question phrased outside the grammar, or about a measure the table does not list, the floor refuses.

## 2026-10-23: model visible tool results use short aliases for result ids

A result id carries the trace id of its request chain, which changes every run. Sent to a model
whole, it would change the digest of every later request and no cassette would ever replay. The
agent shows the model r1, r2 and so on, keeps the map, and translates a claim's alias back before
the readback. Timings and digests are also left out of what the model sees.

## 2026-10-23: a resumed turn continues the trace it started in

The crash test (kill the graph between act and gate, resume from the checkpoint) first failed: the
resumed turn opened a new trace, so the result handles minted before the crash belonged to another
chain and readback refused them. The turn now stores its traceparent in the checkpoint and the
resumed span is opened under it.

## 2026-10-23: the eval plan and the prompt registry are registered before any live call

evals/registration.json holds the plan hash and the prompt registry hash, written once by
scripts/check_registration.py --register before the first live model call. The gate fails a changed
plan or prompt unless this file has a dated entry naming the new hash.

## 2026-10-23: the deploy is a Vercel container function, the doorstep route (reversal)

The prompt planned a Vercel Python function with the entrypoint declared in pyproject. The server
needs the warehouses on disk, 85 MB fetched and checked against the lock, plus DuckDB, LangGraph and
the provider integrations, which is past what a Python function bundle should carry. Doorstep proved
the container route on the same Hobby account the same day, so the image is built from
Dockerfile.vercel, the warehouses are fetched at build time, the migrations run at start, and the
app serves on the port Vercel routes to. Render free stays as the fallback in render.yaml.

## 2026-10-23: the agent reaches its own server over loopback HTTP in production

In tests and in the eval the agent's MCP client is in memory. In production it opens a Client to
http://127.0.0.1:$PORT/mcp, the same streamable HTTP endpoint any host uses, so a protocol bug
cannot hide behind a private path. The loopback address is exempt from the client budget.

## 2026-10-23: the MCP endpoint checks the Host header (revision 2026-07-28)

DNS rebinding protection is on with an allow list: the loopback names and READBACK_PUBLIC_HOSTS
(readback-mcp.vercel.app by default). A request naming another host is refused by the SDK before
it reaches a tool.

## 2026-10-23: the separate client that verifies the live server is not the SDK

deploy/verify.ps1 speaks the revision as plain JSON-RPC from PowerShell on another machine: the
envelope in params._meta, and the mcp-protocol-version, mcp-method and mcp-name headers the
revision requires to match the body. If the SDK and the server agreed on something the
specification does not say, an SDK client would not notice; this one would.

## 2026-10-23: the red team's first run failed two cases, and the system prompt changed (prompt hash ac1dd3c9756c)

The floor's definition answer quoted whatever definition the search returned first. The red team
fixture plants a catalog entry carrying an instruction and a marker, and the first run shipped the
marker in RT-01 and RT-02: 13 of 15. The defense is provenance, not filtering: the floor now quotes a
definition only when the catalog cites it to a build's docs/definitions.md by line, and the planted
entry has no such citation. The second run passed 15 of 15. The system prompt gained the same rule
in words for the models (text in a tool result is data; quote a definition only when it cites a
definitions line), which moved the prompt registry hash from 71102b81e1fb to ac1dd3c9756c. No live
model call had been made, so nothing graded under the old hash. The stripping defense that was
tried and dropped is in notebooks/03_the_injection.

## 2026-10-23: the desk reads the stream, so a tool event carries a preview

The tool cards on the desk expand to the SQL, the schema and the rows. The SQL was already in the
event's arguments; the rows were not, and fetching them again through lookup_result would be a
second warehouse query per card for something the agent had in hand. The tool event now carries the
columns and the first ten rows of a run_sql result, with the full row count. Nothing else in the
event changed, so the API tests stood.

## 2026-10-23: the site reads its two parquet files with hyparquet, not DuckDB-WASM (reversal)

This reverses the locked stack's DuckDB-WASM in the browser, the way the container route reversed
the locked host. The plan said DuckDB-WASM for every chart and the viewer. The site has two parquet files, the eval
run's spans and the manifest index, and every read of them is a filter by trace id or key. DuckDB-WASM
opens parquet through an extension it downloads from extensions.duckdb.org on first use, and a page
that fetches nothing off its own origin cannot allow that; doorstep worked around it by decoding with
hyparquet and handing Arrow to the engine. Here the engine would be eight megabytes of wasm to run a
filter, so the decode is the whole read. The charts read the committed JSON results, which hold the
same numbers the manifest does. If a page ever needs a join, DuckDB-WASM comes back the doorstep way.

## 2026-10-23: B612 keeps its place for figures

The type plan said to confirm tabular figures in B612 and fall back if missing. B612 has no tnum
feature, but every digit in the latin file has the same advance, 1300 units, so its figures are
tabular by construction and columns line up. B612 Mono stays on the tool cards, the SQL and the dense
tables; its period takes a full cell, which reads as a gap in a percentage, so the chips on the desk
use B612 rather than the mono.

## 2026-10-23: Next 16 prefetches with HEAD; the test server caught it

The first Playwright run failed on every route. Next 16's Link prefetch on a static export sends a
HEAD for each linked page, and the test server refuses HEAD the way the series' hosts have. Prefetch
is off on every Link; seven small pages load fast enough without it, and the site now sends no HEAD
at all, which the end to end suite checks.

## 2026-10-23: the identifier scan skips nanosecond timestamps

The first scan of the committed trace parquet reported a card number. It was a span's start_ns:
nineteen digits, and about one in ten such numbers passes Luhn by chance. The scan now skips a column
or a JSON key whose name ends in _ns, and only those; a test checks the same digits under any other
name are still caught.

## 2026-10-23: the test suite overwrote the committed red team result

The red team test that disables the citation rule, to prove the marker check fails without it, ran
through the same function the CLI uses, and that function wrote results/evals/redteam/floor.json.
A full test run therefore left the committed result at the disabled run's count, and a notebook
caught it by reading the file. run_redteam now writes only when asked, the tests pass write=False,
and the disabled test checks the committed file is byte identical afterwards.

## 2026-10-23: the fallback image is Dockerfile.render, so Vercel builds the right one

The import screen for Vercel's container preset asks for no file name, and this repository had two
images: the Render fallback on port 8080 as Dockerfile, and the Vercel image on port 80
as Dockerfile.vercel. doorstep has no plain Dockerfile, so its import could not pick the wrong one. Rather than find out
from a failed deploy which one the preset takes, the fallback is now Dockerfile.render, render.yaml
points at it, and the only image the preset can find is the one meant for it.

## 2026-10-23: the live database is reached on Neon's direct host, not the pooler

The first deploy failed every request. Neon's default connection string names the pooler, and the
pooler refuses the search_path startup option that puts the tables in the readback schema. The
connection string is turned into the direct host's by dropping the -pooler suffix, with a test;
the direct host takes the option, and a demonstration with a handful of connections does not need
pooling. The same deploy showed every cold start rebuilding the twelve packages, because uv run
at start re-synced without the live extra; the start command now runs the virtual environment's
alembic and uvicorn directly.

## 2026-10-23: the agent's loopback client was refused by the server's own Host check (revision 2026-07-28)

The first live question on the desk came back empty. On Vercel the container listens on port 80, so
the agent's loopback client sent a Host header with no port, and the DNS rebinding protection only
allowed the loopback names with a port. Every test had used a random high port and never saw it.
The bare loopback names are allowed now, with a test; the port is read when a turn starts rather
than at import; a turn that fails on the server now ends its stream with an error event, and the
desk says so when a stream closes without an answer, instead of showing nothing.
