---
name: golden-question
description: Add a question to the readback golden set with its known truth, unit, tolerance and split. Use when extending the evaluation, never by editing evals/golden by hand.
license: Apache-2.0
---

# Add a golden question

The golden set is written by `scripts/build_golden.py`; its files are never edited by hand.

1. **Pick the family**: lookup, comparison, trend, top_k, definition, multi or refusal. Each has a
   grader in `packages/evals/src/readback_evals/graders.py`; read the rule for yours.
2. **Name the measure.** A numeric question reads a measure in `catalog/measures.yaml`. If yours
   is not there, add it: the table, the entity and time columns, the aggregate SQL, the display
   format (its rounding sets the tolerance) and the unit. Run the SQL by hand once against the
   warehouse and compare it with a second route to the same number, as `scripts/check_first_ten.py` does.
3. **Add the draw.** Add the measure to the family's list in `main()` of `scripts/build_golden.py`
   for its warehouse. A definition question needs the term and two key phrases that appear verbatim
   in the build's `docs/definitions.md`. A refusal question goes in `REFUSALS`.
4. **Rebuild and check.** `uv run python scripts/build_golden.py`, then
   `uv run pytest tests/data/test_golden.py`. The split is stratified and seeded; adding questions
   moves others between splits, which is why step 5 exists.
5. **Register the change.** The plan in `evals/plan.yaml` names the split sizes. A change to it, or
   to the golden set after results were published, needs a dated `DECISIONS.md` entry naming the
   new plan hash (`uv run python scripts/check_registration.py` prints it), and a full re-run of every
   provider's eval, since grades on the old split do not carry over.

What the grader needs, per question: `claims` (value, unit, fmt, tolerance, the SQL), `entity` for
a comparison, `direction` for a trend, `ranking` for a top k, `key_phrases` for a definition,
`refuse` for a refusal.
