"""Protocol conformance at the 2026-07-28 revision, over the in memory transport."""

from __future__ import annotations

import json
import sys

import jsonschema
import pytest
from mcp import Client, StdioServerParameters
from mcp.shared.exceptions import MCPError
from readback_core.statements import STATEMENT
from readback_mcp_server.server import TOOL_ORDER

from .conftest import TRACEPARENT

VALID_CALLS = {
    "warehouses": {},
    "describe": {"warehouse": "turnaround", "table": "mart_carrier_month"},
    "search_catalog": {"query": "on time rate by carrier", "k": 3},
    "run_sql": {"warehouse": "ledger", "sql": "select period, nim from metrics_bank_quarter order by period"},
    "published": {"warehouse": "doorstep", "key_or_pattern": "ch1.*"},
    "readback": {"claim": {"value": 0.0, "unit": "count", "warehouse": "ledger", "sql": "select 0 as n"}},
    "lookup": {"kind": "carrier", "name": "Delta"},
}


async def test_two_list_calls_return_identical_bytes(client: Client) -> None:
    a = await client.list_tools(cache_mode="refresh")
    b = await client.list_tools(cache_mode="refresh")
    assert a.model_dump_json() == b.model_dump_json()
    assert tuple(t.name for t in a.tools) == TOOL_ORDER


async def test_every_tool_has_an_output_schema_and_its_result_validates(client: Client) -> None:
    tools = {t.name: t for t in (await client.list_tools()).tools}
    assert set(tools) == set(VALID_CALLS)
    for name, args in VALID_CALLS.items():
        assert tools[name].output_schema, name
        result = await client.call_tool(name, args, meta={"traceparent": TRACEPARENT})
        assert not result.is_error, (name, result.content)
        jsonschema.validate(result.structured_content, tools[name].output_schema)
        assert result.structured_content["statement"] == STATEMENT


async def test_list_and_read_results_carry_a_public_hour(client: Client) -> None:
    for result in (
        await client.list_tools(cache_mode="refresh"),
        await client.list_prompts(cache_mode="refresh"),
        await client.list_resource_templates(cache_mode="refresh"),
        await client.read_resource("statement://readback", cache_mode="refresh"),
    ):
        assert result.ttl_ms == 3_600_000 and result.cache_scope == "public"


async def test_discovery_names_the_revision_and_the_identity(client: Client) -> None:
    found = await client.session.discover()
    assert "2026-07-28" in found.supported_versions
    assert client.server_info is not None and client.server_info.name == "readback"
    assert client.protocol_version == "2026-07-28"


async def test_no_deprecated_feature_is_advertised(client: Client) -> None:
    caps = client.server_capabilities.model_dump(exclude_none=True)
    assert "logging" not in caps
    assert "tools" in caps and "resources" in caps and "prompts" in caps


async def test_prompts_validate_their_arguments(client: Client) -> None:
    ok = await client.get_prompt(
        "compare", {"warehouse": "doorstep", "entity_a": "Denver", "entity_b": "Austin"}
    )
    assert "Denver" in json.dumps(ok.model_dump())
    with pytest.raises(MCPError):
        await client.get_prompt("compare", {"warehouse": "nowhere", "entity_a": "a", "entity_b": "b"})


async def test_the_resources_read(client: Client) -> None:
    r = await client.read_resource("catalog://ledger/tables")
    body = json.loads(r.contents[0].text)  # type: ignore[union-attr]
    assert body["warehouse"] == "ledger" and len(body["tables"]) == 75


async def test_stdio_answers_the_same_list(client: Client) -> None:
    params = StdioServerParameters(command=sys.executable, args=["-m", "readback_mcp_server.stdio"])
    async with Client(params) as stdio:
        over_stdio = await stdio.list_tools(cache_mode="refresh")
    in_memory = await client.list_tools(cache_mode="refresh")
    assert [t.model_dump() for t in over_stdio.tools] == [t.model_dump() for t in in_memory.tools]
