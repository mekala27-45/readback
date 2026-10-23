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
