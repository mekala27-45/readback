# Connect a host

The live server speaks the MCP revision 2026-07-28 over streamable HTTP at
https://readback-mcp.vercel.app/mcp, read only, no token. Every block below is rendered from
docs/connect.yaml, the one source the /connect page also reads.

## Claude Desktop, remote

In Settings, Connectors, Add custom connector:

```text
Name: readback
URL: https://readback-mcp.vercel.app/mcp
```

## Claude Desktop, local over stdio

In claude_desktop_config.json:

```json
{
  "mcpServers": {
    "readback": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/readback", "readback-mcp"]
    }
  }
}
```

## claude.ai

In Settings, Connectors, Add custom connector:

```text
Name: readback
URL: https://readback-mcp.vercel.app/mcp
```

## Cursor

In ~/.cursor/mcp.json:

```json
{
  "mcpServers": {
    "readback": { "url": "https://readback-mcp.vercel.app/mcp" }
  }
}
```

## VS Code

In .vscode/mcp.json:

```json
{
  "servers": {
    "readback": { "type": "http", "url": "https://readback-mcp.vercel.app/mcp" }
  }
}
```

## Codex

In ~/.codex/config.toml:

```toml
[mcp_servers.readback]
command = "uv"
args = ["run", "--directory", "/path/to/readback", "readback-mcp"]
```

## Protocol conformance

Revision 2026-07-28; 7 tools, 7 with an
output schema; conformance passed over in memory, stdio, streamable http; an unsupported
version gets error -32,022. results/conformance.json has the run.

The registry entry is server.json, under the io.github namespace of the account. It is published
by hand with a device code login; until then this page says it is not published.

## What the platform engineer would push back on

A public server with no token can be called by anyone, which is why it is read only, why each
client is held to an hourly and a daily budget, and why every query has a row, time and size ceiling.

> Answers are drawn from the published tables of three portfolio builds by Ajay Mekala: doorstep (public housing data from FHFA, the Census Bureau, HUD, the CFPB and Freddie Mac), turnaround (public flight data from the Bureau of Transportation Statistics, the FAA and OurAirports, with weather from Open-Meteo under CC BY 4.0) and ledger (a fictional bank, Harborline, with public HMDA, CFPB, FDIC and macro series). No person appears in any table, and questions are redacted before a model sees them. Every number is read back to the warehouse before it is shown. This is a portfolio demonstration, not financial, travel or lending advice.
