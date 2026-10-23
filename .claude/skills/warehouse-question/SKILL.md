---
name: warehouse-question
description: Answer a question about the doorstep, turnaround or ledger warehouses through the readback MCP tools, with every number read back before it is stated. Use when a task needs a figure from the three warehouses.
license: Apache-2.0
---

# Answer a question against the three warehouses

1. **Place it.** If you do not know which warehouse holds it, call `warehouses`. Refuse, without
   calling another tool, a question about another build, one person, a forecast or advice.
2. **Resolve the names.** Call `lookup` for a metro, carrier, airport, applicant group, AML rule,
   year or quarter. If it returns `needs_choice`, ask the person which candidate they mean.
3. **Find where the number lives.** Call `search_catalog` with the person's words (the synonym
   table maps home price to value_anchored), then `describe` the one table you will use. Note the
   unit of the column.
4. **Get the number.** Call `run_sql` with one SELECT on that warehouse, or `published` for a value
   the build printed. Keep the `result_id`.
5. **Read it back.** For every number you will state, call `readback` with its value, its unit as
   you will write it, the display string, and the `result_id` with `column` and `row` (add
   `evidence_unit` when the column is computed, such as a ratio of two sums). Only an `agree` may
   be stated.
6. **Write it.** Each number exactly as its display string. Years, CBSA and FIPS codes, and the
   numbering of your own list are exempt; nothing else is.

A number that would not read back is not stated. Say what you could not verify instead.
