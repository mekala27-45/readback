"""Where things live. Every path is relative to the repository root, found once."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def root() -> Path:
    env = os.environ.get("READBACK_ROOT")
    if env:
        return Path(env).resolve()
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "data" / "warehouses.lock.json").exists() and (parent / "pyproject.toml").exists():
            return parent
    return Path.cwd().resolve()


def data_dir() -> Path:
    return root() / "data"


def warehouses_dir() -> Path:
    env = os.environ.get("READBACK_WAREHOUSES")
    return Path(env).resolve() if env else data_dir() / "warehouses"


def catalog_dir() -> Path:
    return root() / "catalog"


def results_dir() -> Path:
    return root() / "results"


def evals_dir() -> Path:
    return root() / "evals"


def prompts_dir() -> Path:
    return root() / "prompts"


def providers_dir() -> Path:
    return root() / "providers"
