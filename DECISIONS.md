# Decisions

Dated, newest last. A decision that reversed an earlier one says so and names it. Every decision
that chose a protocol path cites the revision, 2026-07-28, and the reason.

## 2026-10-23: one uv workspace, twelve packages, one direction of import

core, render, catalog, warehouse, gate, tracing, mcp_server, providers, planner, agent, evals and
api. The agent imports the server only to run it in memory in tests; in production it reaches the
server over streamable HTTP like any other host. Nothing imports the api.
