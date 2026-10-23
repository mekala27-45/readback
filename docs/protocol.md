# The protocol

readback implements the Model Context Protocol at revision 2026-07-28 with the official Python SDK
(2.3 at build time). What follows is what a host can rely on, and what was chosen and why.

## Stateless

No session. Each request carries its own envelope in params._meta: the protocol version, the
client's capabilities and its identity, and, over streamable HTTP, the mcp-protocol-version,
mcp-method and mcp-name headers, which must match the body. A request for a version the server does
not support gets error -32022 naming the supported versions. server/discover answers with the
supported revisions, the capabilities and the identity.

The one piece of state that crosses calls is a result handle: run_sql returns a result_id that
carries its own normalized statement, the digest of its rows and the trace id of the caller's request
chain, sealed with an HMAC. readback re-runs it. Nothing is stored on the server.

## Tools, in a committed order

warehouses, describe, search_catalog, run_sql, published, readback, lookup. Every tool is read only
(annotated so), has an input schema and an output schema, and returns structured content that
validates against it. Two tools/list calls return the same bytes; the conformance run checks it.

## Cache hints

tools/list, prompts/list, resources/list, resources/templates/list, resources/read and
server/discover carry ttlMs of an hour and cacheScope public. Nothing in them changes between
deploys or depends on who asked.

## The multi round trip

lookup is the one tool that asks the client something. When a name matches more than one entity and
the client declared the elicitation capability, the server returns an input required result with one
elicitation (an enum of the candidates); the client retries with the answer and the echoed request
state. A client without the capability receives the candidates with needs_choice set.

## Trace context

The server reads traceparent and tracestate from params._meta and opens its span (tools/call
<tool>) as a child of the caller's. One turn of the agent is one trace across the boundary.

## Not implemented, because the revision deprecates it

Roots, sampling and the logging feature. The server never asks a client for a model completion.

## Resources and prompts

catalog://{warehouse}/tables, catalog://{warehouse}/{table}, manifest://{warehouse} and
statement://readback; the prompts analyst_briefing(warehouse) and compare(warehouse, entity_a,
entity_b), whose arguments are validated.

## What the platform engineer would push back on

A stateless server cannot stream progress across requests, so a long query is one request that
either finishes inside ten seconds or is stopped. The handle's seal is an integrity check, not a
secret: its key defaults to a digest of the lock, which is public, and forging one buys only a read
only query the caller could run anyway.
