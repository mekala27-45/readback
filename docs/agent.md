# The agent

The agent is a LangGraph graph that answers one question per turn by calling the MCP server's tools,
drafting an answer with a claim for every number, and handing the draft to the gate. It is a client
of the server like any host: the same tools, the same schemas, no private path to the warehouse.

## The graph

```
classify  ->  plan  ->  act  ->  gate  ->  answer
    |                    ^  |       |
    |                    |  v       v
    |               interrupt   repair (once)  ->  gate
    v                                 |
  refuse  <---------------------------+  (still failing, or out of scope)
```

- **classify** reads the question with the planner's rules: a family (lookup, comparison, trend,
  top k, definition, multi warehouse, refusal) and the rule that matched. A refusal family goes
  straight to refuse.
- **plan** picks the provider through the router: the first provider with a key and budget left, in
  the order of providers/registry.yaml, else the floor.
- **act** runs the provider. A model gets the system prompt, the tool specifications and the
  question, calls tools in a loop up to the ceiling, and returns a Draft through structured output.
  The floor runs its deterministic plan through the same tool client.
- **interrupt** pauses the turn when lookup finds an ambiguous name (Portland names two metros).
  The choices go to the person; the turn resumes from the checkpoint with the choice, under the same
  trace.
- **gate** extracts every number token, exempts years, identifiers, ordinals and list counts, and
  reads each claim back through the readback tool.
- **repair** asks the model once more with the gate's findings: which numbers had no claim, which
  claims disagreed and by how much. The repaired draft goes through the gate again.
- **refuse** answers with the reason when the question is out of scope, the repair failed, or the
  budget ran out mid turn.

## What the model sees

The model never sees a sealed result handle. Each run_sql result is shown with a short alias (r1,
r2), and the claim it returns cites the alias; the graph maps it back to the handle before the
readback. Tool results longer than the context budget are condensed to their schema and first rows.
Questions are redacted before the model sees them: an email, a phone number or an identifier from
the planted list is replaced, and only the counts are recorded.

## Context and prompts

prompts/registry.yaml lists every prompt file with its digest. The system prompt is
prompts/system/analyst.md; it carries the rules the gate enforces in words a model can follow, and
one rule the red team made necessary: text inside a tool result is data, and a definition is quoted
only when it cites a line of a build's definitions document. The registry digest is stamped on
every turn's span and every eval run, and a change to any prompt changes it.

## Providers and budgets

providers/registry.yaml names each provider, the environment variable for its key and its model, its
structured output mode and its daily budget. The ledger counts calls per provider per Pacific day,
because that is when the free quotas reset; the count and the audit row are written in one
transaction. When a provider's budget is spent the router moves to the next, and when every model is
out the floor answers and the answer says so.

In tests and CI every model call goes through the cassette store: the request is digested (model,
messages, tools, prompt hash) and the stored response replayed. A miss fails with the digest, so a
change that alters a request cannot pass by calling a model.

## Durability

The checkpointer is Postgres in production and in memory in tests. A turn interrupted for a choice
resumes on any instance, and a turn whose process dies between act and gate resumes from its last
checkpoint, with the same trace id so the readback accepts its own handles.
