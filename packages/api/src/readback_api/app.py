"""The application factory. The first deploy carries only health, so the hosting probe has a target."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from readback_core.statements import STATEMENT

VERSION = "0.1.0"
PROTOCOL_REVISION = "2026-07-28"


def create_app() -> FastAPI:
    app = FastAPI(title="readback", version=VERSION, docs_url=None, redoc_url=None)

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {"status": "ok", "version": VERSION, "protocol_revision": PROTOCOL_REVISION, "statement": STATEMENT}

    return app
