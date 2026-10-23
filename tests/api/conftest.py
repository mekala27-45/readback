from __future__ import annotations

import os
import socket
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import pytest


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@pytest.fixture(scope="session")
def live(tmp_path_factory: pytest.TempPathFactory) -> Iterator[dict[str, object]]:
    """The API in a uvicorn thread on a free port, with its own SQLite answer log."""
    import uvicorn

    db = Path(tmp_path_factory.mktemp("api")) / "readback.sqlite"
    port = free_port()
    saved = {k: os.environ.get(k) for k in ("PORT", "READBACK_SQLITE", "DATABASE_URL")}
    os.environ.update({"PORT": str(port), "READBACK_SQLITE": str(db)})
    os.environ.pop("DATABASE_URL", None)
    from readback_api.app import create_app

    server = uvicorn.Server(uvicorn.Config(create_app(), host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(300):
        if server.started:
            break
        time.sleep(0.05)
    yield {"url": f"http://127.0.0.1:{port}", "db": db}
    server.should_exit = True
    thread.join(timeout=10)
    for k, v in saved.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
