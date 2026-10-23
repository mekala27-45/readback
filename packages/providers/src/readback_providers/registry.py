"""The provider registry, providers/registry.yaml, read into one model per provider."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

import yaml
from readback_core import paths
from readback_core.model import StrictModel

FLOOR = "floor"


class Provider(StrictModel):
    name: str
    key_env: str | None
    model_env: str | None = None
    fallback_env: str | None = None
    model: str
    base_url: str | None = None
    structured: Literal["schema", "tools", "none"]
    daily_budget: int | None
    per_minute: int | None
    terms_allow_public_aggregates: bool
    integration: str
    local_only: bool = False

    @property
    def is_floor(self) -> bool:
        return self.name == FLOOR

    def has_key(self) -> bool:
        if self.is_floor:
            return True
        if self.local_only and os.environ.get("CI"):
            return False
        return bool(self.key_env and os.environ.get(self.key_env))

    def model_id(self) -> str:
        if self.model_env and os.environ.get(self.model_env):
            return str(os.environ[self.model_env])
        return self.model


def load(path: Path | None = None) -> list[Provider]:
    raw = yaml.safe_load((path or paths.providers_dir() / "registry.yaml").read_text(encoding="utf-8"))
    out = [Provider.model_validate(p) for p in raw["providers"]]
    if not out or not out[-1].is_floor:
        raise ValueError("the floor must be the last provider in the registry")
    if not all(p.terms_allow_public_aggregates for p in out):
        raise ValueError("every provider must allow the data readback sends")
    return out
