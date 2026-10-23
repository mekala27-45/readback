"""The agent's side of the protocol: every tool call goes to the MCP server through a Client.

In tests and in the eval the client is connected in memory; in production it reaches the server over
streamable HTTP. Each call carries traceparent and tracestate in its request metadata, so the
server's span is a child of the agent's execute_tool span, and each result is kept with an id and
the digest the server returned.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import Any

from mcp import Client
from readback_tracing import carrier, tool_span

WAREHOUSE_TOOLS = frozenset({"describe", "search_catalog", "run_sql", "published", "readback", "lookup", "warehouses"})


class ToolError(RuntimeError):
    def __init__(self, tool: str, message: str) -> None:
        super().__init__(f"{tool}: {message}")
        self.tool = tool
        self.message = message


@dataclass
class ToolRecord:
    id: str
    tool: str
    args: dict[str, Any]
    ok: bool
    result: dict[str, Any] | None
    error: str | None
    digest: str | None


@dataclass
class ToolClient:
    client: Client
    records: list[ToolRecord] = field(default_factory=list)
    ceiling: int | None = None
    _ids: Any = field(default_factory=lambda: itertools.count(1))

    @property
    def calls(self) -> int:
        return len(self.records)

    def warehouse_calls(self) -> int:
        return sum(1 for r in self.records if r.tool in WAREHOUSE_TOOLS and r.tool != "readback")

    async def call(self, tool: str, args: dict[str, Any]) -> dict[str, Any]:
        call_id = f"t{next(self._ids)}"
        if self.ceiling is not None and self.warehouse_calls() >= self.ceiling and tool != "readback":
            self.records.append(ToolRecord(call_id, tool, args, False, None, "tool call ceiling", None))
            raise ToolError(tool, f"the tool call ceiling of {self.ceiling} for one turn was reached")
        with tool_span(tool, call_id):
            result = await self.client.call_tool(tool, args, meta=carrier())  # type: ignore[arg-type]
        if result.is_error:
            text = " ".join(getattr(c, "text", "") for c in result.content)
            self.records.append(ToolRecord(call_id, tool, args, False, None, text, None))
            raise ToolError(tool, text)
        content = dict(result.structured_content or {})
        self.records.append(ToolRecord(call_id, tool, args, True, content, None, content.get("digest")))
        return content
