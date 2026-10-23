"""Cassettes: every model request in the test suite and the eval replays from a recorded response.

A request is keyed by a digest of the provider, the model, the prompt registry hash and the message
list in a canonical form (tool results have their volatile fields removed and result ids replaced by
the per turn aliases the model sees, so a replay produces the same key). A recorded response replays.
A miss in CI fails with the digest printed. A miss in a live run calls the provider within its
budget and records the response, with the recording date and the model id the provider reported.
"""

from __future__ import annotations

import datetime as dt
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from readback_core import paths
from readback_core.hashing import sha256_json


class CassetteMiss(LookupError):
    def __init__(self, provider: str, digest: str) -> None:
        super().__init__(f"no cassette for {provider} request {digest}; record it with scripts/record_cassettes.py")
        self.provider = provider
        self.digest = digest


def mode() -> str:
    """replay in CI and by default; record only when READBACK_CASSETTES=record and a key is present."""
    return os.environ.get("READBACK_CASSETTES", "replay")


def message_form(message: Any) -> dict[str, Any]:
    """A LangChain message in the canonical form the digest is taken over."""
    kind = getattr(message, "type", "unknown")
    out: dict[str, Any] = {"type": kind, "content": message.content if isinstance(message.content, str) else json.dumps(message.content, sort_keys=True)}
    calls = getattr(message, "tool_calls", None)
    if calls:
        out["tool_calls"] = [{"name": c["name"], "args": c["args"], "id": c.get("id")} for c in calls]
    if kind == "tool":
        out["tool_call_id"] = getattr(message, "tool_call_id", None)
    return out


def request_digest(provider: str, model: str, prompt_hash: str, messages: list[Any], tools: list[dict[str, Any]] | None = None) -> str:
    return sha256_json({
        "provider": provider,
        "model": model,
        "prompt_hash": prompt_hash,
        "messages": [message_form(m) for m in messages],
        "tools": sorted(t["function"]["name"] for t in tools or []),
    })


@dataclass
class Cassette:
    provider: str
    model_requested: str
    model_reported: str | None
    recorded_at: str
    prompt_hash: str
    digest: str
    response: dict[str, Any]

    def write(self, root: Path) -> Path:
        path = root / self.provider / f"{self.digest}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.__dict__, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        return path


class Store:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or paths.evals_dir() / "cassettes"
        self.hits = 0
        self.misses = 0

    def get(self, provider: str, digest: str) -> Cassette | None:
        path = self.root / provider / f"{digest}.json"
        if not path.exists():
            return None
        self.hits += 1
        return Cassette(**json.loads(path.read_text(encoding="utf-8")))

    def put(self, provider: str, model: str, reported: str | None, prompt_hash: str, digest: str, response: dict[str, Any]) -> Cassette:
        c = Cassette(provider, model, reported, dt.datetime.now(dt.UTC).date().isoformat(), prompt_hash, digest, response)
        c.write(self.root)
        return c

    def dates(self, provider: str) -> list[str]:
        folder = self.root / provider
        if not folder.exists():
            return []
        return sorted({json.loads(p.read_text(encoding="utf-8"))["recorded_at"] for p in folder.glob("*.json")})
