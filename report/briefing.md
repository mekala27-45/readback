# readback: the briefing

*For a hiring manager or a platform lead with ten minutes. Every figure below is rendered from
results/manifest.json; the claim gate fails the build if this page says a number the manifest does
not hold.*

## The question this build answers

Can an analyst agent be trusted with a number? Not in general. In this build, a number is trusted
when plain code has read it back to the warehouse it came from, in the unit it claims, within half
the rounding it is shown at. Everything else follows from that rule: the gate, the refusals, the
floor, the scorecard.

## What was measured

| | |
|---|---|
| Published tables in reach | 163 across doorstep, turnaround and ledger |
| Measure columns with a unit | 1,105 of 1,105 |
| Measure columns with a cited definition | 657 |
| Golden questions | 150, split 50 development and 100 test |
| Floor accuracy on the test split | 98.0%, interval 93.0% to 99.4% |
| Shipped numbers read back | 100.0% of 174 |
| Red team cases passed on the floor | 15 of 15 |
| Protocol conformance | passed over in memory, stdio, streamable http |
| The live endpoint | not yet verified |

## Three findings

**The gate earns its place on the catalog, not on the arithmetic.** The first catalog build tagged a
ratio column as dollars. No test caught it; the readback did, because a ratio read back in dollars
never agrees. Unit rules are now table specific and ordered, and a range check quarantines any
column whose values do not fit its unit. The quarantine is 2,129 named rows
rather than a guess.

**A red team case is a catalog problem before it is a prompt problem.** The first red team run on
the floor passed fewer cases than it does now, because the floor quoted a planted definition from the
catalog. The fix was a provenance rule: the floor quotes only definitions cited to a line of a build's
own documents. The system prompt got the same rule, which changed the prompt hash; DECISIONS.md
records it.

**The floor is a ceiling, not a rival.** The floor and the golden truth read one measures table, so
its row is the best the in scope families can do, and a model is called better only when its
interval clears the floor's. gemini, groq, openrouter, sambanova, ollama have not run yet on a free key; their
rows appear when their cassettes exist, and never from a partial run.

## What I would push back on, as the reviewer

The known answers are this portfolio's own published numbers, so the eval measures reading, not
truth. The gate checks that a number agrees with the query it cites, not that the query was the right
one; the graders check that separately. A free quota bounds how much of the test split a model sees,
and the scorecard prints that share beside every row.

## Where to look next

The desk at https://mekala27-45.github.io/readback/ answers live when the API is awake and from a
labeled recording when it is not. The scorecard, the traces and the catalog are pages beside it.
docs/SPEC.md is the specification; DECISIONS.md is the record of what changed and why.

> Answers are drawn from the published tables of three portfolio builds by Ajay Mekala: doorstep (public housing data from FHFA, the Census Bureau, HUD, the CFPB and Freddie Mac), turnaround (public flight data from the Bureau of Transportation Statistics, the FAA and OurAirports, with weather from Open-Meteo under CC BY 4.0) and ledger (a fictional bank, Harborline, with public HMDA, CFPB, FDIC and macro series). No person appears in any table, and questions are redacted before a model sees them. Every number is read back to the warehouse before it is shown. This is a portfolio demonstration, not financial, travel or lending advice.
