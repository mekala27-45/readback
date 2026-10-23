"""The console script readback-mcp: the server over stdio, for editors and Claude Desktop."""

from __future__ import annotations

from readback_mcp_server.server import build_server


def main() -> None:
    build_server().run("stdio")


if __name__ == "__main__":
    main()
