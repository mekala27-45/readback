from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from mcp import Client
from readback_agent.run import Agent
from readback_mcp_server.server import build_server
from readback_providers.cassettes import Store
from readback_tracing import install


@pytest.fixture(scope="session")
def server():  # type: ignore[no-untyped-def]
    return build_server()


@pytest.fixture
async def client(server) -> AsyncIterator[Client]:  # type: ignore[no-untyped-def]
    async with Client(server) as c:
        yield c


@pytest.fixture
def exporter():  # type: ignore[no-untyped-def]
    e = install()
    e.clear()
    return e


@pytest.fixture
def scripted_agent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    monkeypatch.setenv("GROQ_API_KEY", "test")
    monkeypatch.setenv("READBACK_CASSETTES", "record")

    def make(fake):  # type: ignore[no-untyped-def]
        return Agent(store=Store(tmp_path / "cassettes"), model_factory=lambda p: fake)

    return make
