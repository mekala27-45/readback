"""The console script readback-mcp: the server over stdio, for editors and Claude Desktop.

A fresh clone has no warehouses on disk; the first run fetches them from the pinned tags and checks
every file against the lock before the server starts.
"""

from __future__ import annotations

import subprocess
import sys

from readback_core import paths

from readback_mcp_server.server import build_server


def main() -> None:
    lock = paths.root() / "data" / "warehouses.lock.json"
    script = paths.root() / "scripts" / "fetch_warehouses.py"
    if lock.exists() and script.exists() and not (paths.warehouses_dir() / "doorstep").exists():
        subprocess.run([sys.executable, str(script), "--quiet"], check=True, stdout=sys.stderr)
    build_server().run("stdio")


if __name__ == "__main__":
    main()
