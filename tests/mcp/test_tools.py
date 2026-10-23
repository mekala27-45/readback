"""Each tool's refusals and the readback rules, through the protocol."""

from __future__ import annotations

from typing import Any

from mcp import Client
from mcp_types import ElicitResult
from readback_mcp_server.server import build_server

from .conftest import TRACEPARENT

OTHER = "00-11111111111111111111111111111111-2222222222222222-01"


async def call(client: Client, name: str, args: dict[str, Any], parent: str = TRACEPARENT) -> Any:
    return await client.call_tool(name, args, meta={"traceparent": parent})


async def test_describe_refuses_an_unknown_table_with_three_near_names(client: Client) -> None:
    r = await call(client, "describe", {"warehouse": "doorstep", "table": "ch5_rank"})
    assert r.is_error and "ch5_ranking" in r.content[0].text


async def test_search_caps_k_and_returns_the_expanded_query(client: Client) -> None:
    r = await call(client, "search_catalog", {"query": "house price", "k": 500})
    sc = r.structured_content
    assert len(sc["hits"]) <= 20 and "anchored" in sc["expanded"]


async def test_published_caps_at_fifty_and_sorts(client: Client) -> None:
    r = await call(client, "published", {"warehouse": "ledger", "key_or_pattern": "f0*"})
    sc = r.structured_content
    keys = [v["key"] for v in sc["values"]]
    assert len(keys) == 50 and keys == sorted(keys) and sc["matches"] > 50


async def test_readback_agrees_within_half_a_unit_of_the_published_rounding(client: Client) -> None:
    pub = await call(client, "published", {"warehouse": "ledger", "key_or_pattern": "f01.nim_q"})
    v = pub.structured_content["values"][0]
    assert v["display"] == "5.60%"
    ok = await call(client, "readback", {"claim": {"value": 5.6, "unit": "percent", "warehouse": "ledger", "manifest_key": "f01.nim_q"}})
    assert ok.structured_content["verdict"] == "agree"
    off = await call(client, "readback", {"claim": {"value": 5.61, "unit": "percent", "warehouse": "ledger", "manifest_key": "f01.nim_q"}})
    assert off.structured_content["verdict"] == "disagree"


async def test_readback_converts_a_percent_and_refuses_a_dollar_against_a_fraction(client: Client) -> None:
    as_fraction = await call(client, "readback", {"claim": {"value": 0.056, "unit": "fraction", "warehouse": "ledger", "manifest_key": "f01.nim_q"}})
    assert as_fraction.structured_content["verdict"] == "agree"
    mismatch = await call(client, "readback", {"claim": {"value": 0.056, "unit": "dollars", "warehouse": "ledger", "manifest_key": "f01.nim_q"}})
    assert mismatch.structured_content["verdict"] == "unit mismatch"


async def test_readback_finds_a_result_id_in_its_chain_and_refuses_a_foreign_one(client: Client) -> None:
    run = await call(client, "run_sql", {"warehouse": "turnaround", "sql": "select sum(on_time) / sum(flown) as rate from mart_carrier_month where carrier = 'DL' and year = 2019"})
    rid = run.structured_content["result_id"]
    value = run.structured_content["rows"][0][0]
    claim = {"value": round(value * 100, 1), "unit": "percent", "display": f"{value * 100:.1f}%", "result_id": rid, "column": "rate", "evidence_unit": "fraction"}
    mine = await call(client, "readback", {"claim": claim})
    assert mine.structured_content["verdict"] == "agree" and mine.structured_content["unit_source"] == "declared"
    foreign = await call(client, "readback", {"claim": claim}, parent=OTHER)
    assert foreign.structured_content["verdict"] == "refused" and "another request chain" in foreign.structured_content["reason"]
    tampered = dict(claim, result_id=rid[:-2] + ("00" if not rid.endswith("00") else "11"))
    bad = await call(client, "readback", {"claim": tampered})
    assert bad.structured_content["verdict"] == "refused"


async def test_readback_needs_exactly_one_source(client: Client) -> None:
    r = await call(client, "readback", {"claim": {"value": 1.0, "unit": "count"}})
    assert r.structured_content["verdict"] == "refused"


async def test_run_sql_refuses_with_the_clause_named(client: Client) -> None:
    r = await call(client, "run_sql", {"warehouse": "doorstep", "sql": "select * from turnaround.mart_carrier_month"})
    assert r.is_error and "turnaround.mart_carrier_month" in r.content[0].text


async def test_lookup_asks_through_the_round_trip_when_the_client_can_be_asked() -> None:
    asked: list[str] = []

    async def elicit(ctx: Any, params: Any) -> ElicitResult:
        asked.append(params.message)
        assert params.requested_schema["properties"]["choice"]["enum"]
        return ElicitResult(action="accept", content={"choice": "Portland-Vancouver-Hillsboro, OR-WA"})

    async with Client(build_server(), elicitation_callback=elicit) as c:
        r = await c.call_tool("lookup", {"kind": "metro", "name": "Portland"})
    assert asked and r.structured_content["resolved"] == "Portland-Vancouver-Hillsboro, OR-WA"


async def test_lookup_returns_candidates_when_the_client_cannot_be_asked(client: Client) -> None:
    r = await call(client, "lookup", {"kind": "metro", "name": "Portland"})
    sc = r.structured_content
    assert sc["needs_choice"] and sc["resolved"] is None and len(sc["candidates"]) == 2


async def test_lookup_resolves_names_the_way_the_warehouse_spells_them(client: Client) -> None:
    for kind, name, want in [("carrier", "Delta Air Lines", "DL"), ("metro", "Denver", "Denver-Aurora-Centennial, CO"),
                             ("airport", "LaGuardia", "LGA"), ("quarter", "the second quarter of 2025", "2025Q2"),
                             ("aml_rule", "money mule", "mule")]:
        r = await call(client, "lookup", {"kind": kind, "name": name})
        assert r.structured_content["resolved"] == want, (kind, name)
