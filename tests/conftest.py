from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("READBACK_ROOT", str(ROOT))


import inspect

import pytest


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Run every coroutine test under anyio, so an async fixture enters and exits in one task."""
    for item in items:
        fn = getattr(item, "function", None)
        if fn is not None and inspect.iscoroutinefunction(fn):
            item.add_marker(pytest.mark.anyio)
