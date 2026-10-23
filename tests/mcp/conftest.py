from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from mcp import Client
from readback_mcp_server.server import build_server

TRACEPARENT = "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"


@pytest.fixture(scope="session")
def server():  # type: ignore[no-untyped-def]
    return build_server()


@pytest.fixture
async def client(server) -> AsyncIterator[Client]:  # type: ignore[no-untyped-def]
    async with Client(server) as c:
        yield c
