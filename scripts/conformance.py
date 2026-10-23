"""The protocol conformance summary: results/conformance.json.

Runs the server three ways (in memory, over stdio as a subprocess, over streamable HTTP as a uvicorn
process) and records what a reader of the connect page needs: the revision, the discovery result,
the tool count, whether every tool has an output schema, whether two lists are byte identical,
whether every list carries its cache hint, the unsupported version error, whether both transports
answer the same list, and whether the server's span is a child of the caller's.
"""

from __future__ import annotations

import asyncio
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import httpx
from mcp import Client, StdioServerParameters
from readback_mcp_server.server import PROTOCOL_REVISION, build_server
from readback_tracing import carrier, install, tool_span


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


async def run() -> dict[str, object]:
    exporter = install()
    exporter.clear()
    server = build_server()
    out: dict[str, object] = {"revision": PROTOCOL_REVISION}
    async with Client(server) as c:
        discover = await c.session.discover()
        out["discovery"] = {
            "supported_versions": list(discover.supported_versions),
            "server": c.server_info.name if c.server_info else None,
            "capabilities": sorted(
                k for k, v in discover.capabilities.model_dump(exclude_none=True).items() if v is not None
            ),
        }
        a = await c.list_tools(cache_mode="refresh")
        b = await c.list_tools(cache_mode="refresh")
        out["tools"] = [t.name for t in a.tools]
        out["tool_count"] = len(a.tools)
        out["output_schemas"] = sum(1 for t in a.tools if t.output_schema)
        out["lists_identical"] = a.model_dump_json() == b.model_dump_json()
        hints = [
            a,
            await c.list_prompts(cache_mode="refresh"),
            await c.list_resource_templates(cache_mode="refresh"),
            await c.read_resource("statement://readback", cache_mode="refresh"),
        ]
        out["cache_hints"] = all(h.ttl_ms == 3_600_000 and h.cache_scope == "public" for h in hints)
        out["deprecated_advertised"] = "logging" in c.server_capabilities.model_dump(exclude_none=True)
        with tool_span("warehouses", "conformance") as span:
            parent = format(span.get_span_context().span_id, "016x")
            trace_id = format(span.get_span_context().trace_id, "032x")
            await c.call_tool("warehouses", {}, meta=carrier())  # type: ignore[arg-type]
        rows = exporter.rows(trace_id)
        server_span = next((r for r in rows if r["name"] == "tools/call warehouses"), None)
        out["trace_context"] = bool(server_span and server_span["parent_id"] == parent)
        memory_list = [t.model_dump() for t in a.tools]
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "readback_mcp_server.stdio"], cwd=str(ROOT)
    )
    async with Client(params) as s:
        stdio_list = [t.model_dump() for t in (await s.list_tools(cache_mode="refresh")).tools]
    port = free_port()
    env = {**os.environ, "PORT": str(port), "READBACK_SQLITE": str(Path(tempfile.mkdtemp()) / "c.sqlite")}
    env.pop("DATABASE_URL", None)
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "readback_api.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        base = f"http://127.0.0.1:{port}"
        for _ in range(240):
            try:
                if httpx.get(f"{base}/health", timeout=2).status_code == 200:
                    break
            except httpx.HTTPError:
                time.sleep(0.5)
        async with Client(f"{base}/mcp") as h:
            http_list = [t.model_dump() for t in (await h.list_tools(cache_mode="refresh")).tools]
        meta = {
            "io.modelcontextprotocol/protocolVersion": "1999-01-01",
            "io.modelcontextprotocol/clientCapabilities": {},
        }
        r = httpx.post(
            f"{base}/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {"_meta": meta}},
            headers={
                "accept": "application/json, text/event-stream",
                "mcp-protocol-version": "1999-01-01",
                "mcp-method": "tools/list",
            },
        )
        out["unsupported_version_error"] = r.json().get("error", {}).get("code")
    finally:
        proc.terminate()
        proc.wait(timeout=20)
    out["transports"] = {
        "in_memory": True,
        "stdio": stdio_list == memory_list,
        "streamable_http": http_list == memory_list,
    }
    out["passed"] = bool(
        out["lists_identical"]
        and out["output_schemas"] == out["tool_count"] == 7
        and out["cache_hints"]
        and not out["deprecated_advertised"]
        and out["trace_context"]
        and out["unsupported_version_error"] == -32022
        and all(out["transports"].values())
    )  # type: ignore[union-attr]
    return out


if __name__ == "__main__":
    result = asyncio.run(run())
    path = ROOT / "results" / "conformance.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=1))
    sys.exit(0 if result["passed"] else 1)
