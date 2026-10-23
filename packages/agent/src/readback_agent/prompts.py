"""The prompt registry: every system prompt and tool description is a file with a hash.

prompts/registry.yaml lists the files; each is hashed, and the registry is hashed as a whole. The
hash is recorded in every trace and printed on the scorecard. A prompt changed after the eval plan
was registered changes the hash and fails scripts/check_registration.py unless DECISIONS.md carries
a dated entry naming the new hash.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml
from readback_core import paths
from readback_core.hashing import sha256_json, sha256_text, short


@dataclass(frozen=True)
class Registry:
    files: dict[str, str]  # name -> text
    hashes: dict[str, str]
    digest: str

    def text(self, name: str) -> str:
        return self.files[name]

    @property
    def short(self) -> str:
        return short(self.digest)


def build(root: Path | None = None) -> Registry:
    base = (root or paths.root()) / "prompts"
    listed = yaml.safe_load((base / "registry.yaml").read_text(encoding="utf-8"))["prompts"]
    files: dict[str, str] = {}
    hashes: dict[str, str] = {}
    for entry in listed:
        text = (base / entry["file"]).read_text(encoding="utf-8")
        files[entry["name"]] = text
        hashes[entry["name"]] = sha256_text(text)
    return Registry(files, hashes, sha256_json(hashes))


@lru_cache(maxsize=1)
def registry() -> Registry:
    return build()
