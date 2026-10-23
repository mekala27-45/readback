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
