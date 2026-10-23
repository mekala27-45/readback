"""The readback MCP server at protocol revision 2026-07-28.

One server object, two transports: stdio through the console script readback-mcp, and streamable
HTTP as an ASGI app the API mounts at /mcp. Stateless, as the revision requires: no session, the
protocol version and the client capabilities read from each request's metadata, server discovery
answered by the SDK with the supported revisions, the capabilities and the identity.

Tools are registered in the fixed order of TOOL_ORDER, so two list calls return the same bytes.
Every list and read result carries a cache hint of one hour, public, because the catalog and the
published values do not change between deploys. Every tool returns a Pydantic model, which gives it
an output schema and structured content that validates against it.

Nothing deprecated under the revision is implemented: no roots, no sampling, no logging feature.
The one server to client request is an elicitation inside an input required result, the revision's
multi round trip pattern, used by lookup when a name is ambiguous.
"""


import json
from pathlib import Path
from typing import Annotated, Any, Literal

from mcp.server.caching import CacheHint
from mcp.server.mcpserver import Context, Elicit, MCPServer, Resolve
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.mcpserver.prompts.base import Message, UserMessage
from mcp_types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, create_model
from readback_core import paths
from readback_core.statements import STATEMENT

from readback_mcp_server import tools as t
from readback_mcp_server.schemas import (
    Claim,
    DescribeOut,
    LookupOut,
    PublishedOut,
    ReadbackOut,
    RunSqlOut,
    SearchOut,
    WarehouseName,
    WarehousesOut,
)
from readback_mcp_server.state import State, shared_state

PROTOCOL_REVISION = "2026-07-28"
VERSION = "0.1.0"
TOOL_ORDER: tuple[str, ...] = ("warehouses", "describe", "search_catalog", "run_sql", "published", "readback", "lookup")
HOUR_MS = 3_600_000
CACHE_HINTS = {
    method: CacheHint(ttl_ms=HOUR_MS, scope="public")
    for method in ("tools/list", "resources/list", "resources/read", "resources/templates/list", "prompts/list", "server/discover")
}
READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
INSTRUCTIONS = (
    "Three published warehouses (doorstep, turnaround, ledger), read only. Find a number with search_catalog "
    "and describe, get it with run_sql or published, and call readback on every number before you say it."
)

Kind = Literal["metro", "carrier", "airport", "applicant_group", "aml_rule", "year", "quarter", "county"]


def tool_description(name: str) -> str:
    return (paths.prompts_dir() / "tools" / f"{name}.md").read_text(encoding="utf-8").strip()


def chain_of(ctx: Context | None) -> str:
    """The request chain a result handle is bound to: the trace id the caller sent, or anonymous."""
    meta = _meta(ctx)
    parent = meta.get("traceparent")
    if isinstance(parent, str) and parent.count("-") == 3:
        return parent.split("-")[1]
    return "anonymous"


def _meta(ctx: Context | None) -> dict[str, Any]:
    if ctx is None:
        return {}
    try:
        meta = ctx.request_context.meta
    except (AttributeError, LookupError, ValueError):
        return {}
    if meta is None:
        return {}
    return dict(meta) if not isinstance(meta, dict) else meta


def can_elicit(ctx: Context | None) -> bool:
    caps = _meta(ctx).get("io.modelcontextprotocol/clientCapabilities") or {}
    return isinstance(caps, dict) and bool(caps.get("elicitation"))


class Choice(BaseModel):
    model_config = ConfigDict(extra="forbid")
    choice: str


def build_server(state: State | None = None) -> MCPServer:
    st = state or shared_state()
    server = MCPServer(
        "readback",
        title="readback",
        description="An analyst's tools over three published warehouses, with a readback for every number.",
        instructions=INSTRUCTIONS,
        website_url="https://mekala27-45.github.io/readback/",
        version=VERSION,
        cache_hints=CACHE_HINTS,
        subscriptions=False,
        log_level="WARNING",
    )

    def refuse(err: Exception) -> ToolError:
        return ToolError(str(err))

    # The tools, in TOOL_ORDER.

    def warehouses() -> WarehousesOut:
        return t.warehouses(st)

    def describe(warehouse: WarehouseName, table: str) -> DescribeOut:
        try:
            return t.describe(st, warehouse, table)
        except t.ToolRefusal as err:
            raise refuse(err) from err

    def search_catalog(query: str, k: int = 8, warehouse: WarehouseName | None = None) -> SearchOut:
        try:
            return t.search_catalog(st, query, k, warehouse)
        except t.ToolRefusal as err:
            raise refuse(err) from err

    def run_sql(warehouse: WarehouseName, sql: str, ctx: Context, limit: int | None = None) -> RunSqlOut:
        try:
            return t.run_sql(st, warehouse, sql, limit, chain_of(ctx))
        except t.ToolRefusal as err:
            raise refuse(err) from err

    def published(warehouse: WarehouseName, key_or_pattern: str) -> PublishedOut:
        try:
            return t.published(st, warehouse, key_or_pattern)
        except t.ToolRefusal as err:
            raise refuse(err) from err

    def readback(claim: Claim, ctx: Context) -> ReadbackOut:
        return t.readback(st, claim, chain_of(ctx))

    def resolve_choice(kind: str, name: str, ctx: Context) -> Any:
        try:
            resolved, cands = t.candidates(st, kind, name)
        except t.ToolRefusal as err:
            raise refuse(err) from err
        if resolved is not None or len(cands) < 2 or not can_elicit(ctx):
            return Choice(choice=resolved or "")
        values = tuple(c.value for c in cands)
        model = create_model("Choice", __base__=Choice, choice=(Literal[values], ...))  # type: ignore[valid-type]
        return Elicit(f"{name!r} matches {len(values)} {kind}s in the warehouses. Which one did you mean?", model)

    def lookup(kind: Kind, name: str, chosen: Annotated[Choice, Resolve(resolve_choice)], ctx: Context) -> LookupOut:
        resolved, cands = t.candidates(st, kind, name)
        if resolved is None and chosen.choice:
            return t.lookup_result(kind, name, chosen.choice, cands, asked=True)
        return t.lookup_result(kind, name, resolved, cands, asked=False)

    for fn in (warehouses, describe, search_catalog, run_sql, published, readback, lookup):
        server.add_tool(fn, name=fn.__name__, description=tool_description(fn.__name__), annotations=READ_ONLY,
                        structured_output=True)
    listed = [tool.name for tool in server._tool_manager.list_tools()]  # noqa: SLF001
    if tuple(listed) != TOOL_ORDER:
        raise RuntimeError(f"the tools registered out of their committed order: {listed}")

    # Resources and templates.

    @server.resource("statement://readback", name="statement", mime_type="text/plain",
                     description="The statement every surface of readback carries.")
    def statement_resource() -> str:
        return STATEMENT

    @server.resource("catalog://{warehouse}/tables", name="tables", mime_type="application/json",
                     description="Every table of a warehouse with its grain and row count.")
    def tables_resource(warehouse: str) -> str:
        if warehouse not in st.catalogs:
            raise ValueError(f"there is no warehouse {warehouse!r}")
        c = st.catalogs[warehouse]
        rows = [{"table": x.name, "grain": x.grain, "rows": x.rows, "source_step": x.source_step} for x in c.tables]
        return json.dumps({"warehouse": warehouse, "tag": c.tag, "tables": rows, "statement": STATEMENT})

    @server.resource("catalog://{warehouse}/{table}", name="table", mime_type="application/json",
                     description="One table's catalog entry: grain, columns, units and definitions.")
    def table_resource(warehouse: str, table: str) -> str:
        if warehouse not in st.catalogs or st.catalogs[warehouse].table(table) is None:
            raise ValueError(f"there is no table {warehouse}.{table}")
        entry = st.catalogs[warehouse].table(table)
        assert entry is not None
        return entry.model_dump_json()

    @server.resource("manifest://{warehouse}", name="manifest", mime_type="application/json",
                     description="The numeric values a warehouse's manifest publishes, with units and rounding.")
    def manifest_resource(warehouse: str) -> str:
        if warehouse not in st.manifest:
            raise ValueError(f"there is no warehouse {warehouse!r}")
        values = [
            {"key": e.key, "value": e.value, "unit": e.unit, "rounding": e.step}
            for e in st.manifest[warehouse].values()
            if e.value is not None
        ]
        return json.dumps({"warehouse": warehouse, "values": values, "statement": STATEMENT})

    # Prompts, with validated arguments.

    @server.prompt(name="analyst_briefing", description="Brief an analyst on one warehouse: what it covers and where its numbers live.")
    def analyst_briefing(warehouse: str) -> list[Message]:
        if warehouse not in st.catalogs:
            raise ValueError("warehouse must be doorstep, turnaround or ledger")
        c = st.catalogs[warehouse]
        return [UserMessage(
            f"Brief me on the {warehouse} warehouse ({c.covers}). Call warehouses, then search_catalog and "
            f"describe for its three most used tables, and read back every number you state."
        )]

    @server.prompt(name="compare", description="Compare two entities of one warehouse on its published measures.")
    def compare(warehouse: str, entity_a: str, entity_b: str) -> list[Message]:
        if warehouse not in st.catalogs:
            raise ValueError("warehouse must be doorstep, turnaround or ledger")
        if not entity_a.strip() or not entity_b.strip() or entity_a.strip() == entity_b.strip():
            raise ValueError("entity_a and entity_b must be two different names")
        return [UserMessage(
            f"In {warehouse}, compare {entity_a} with {entity_b}. Resolve both with lookup first, use the same "
            f"table and year for both, and read back every number."
        )]

    return server


def server_root() -> Path:
    return paths.root()
