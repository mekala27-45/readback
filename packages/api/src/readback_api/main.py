"""The ASGI entrypoint the host imports: ``readback_api.main:app``."""

from __future__ import annotations

from readback_api.app import create_app

app = create_app()
