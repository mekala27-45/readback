"""The golden set: 150 questions with known answers, committed before the agent existed.

Each in scope question carries its known answer as claims (a value, a unit, a tolerance, and the
SQL over the published tables or the manifest key that produced it), plus what its family grades:
the entity a comparison names, the direction of a trend, the ordered set of a top k, the key phrases
of a definition. A refusal question carries only that it must be refused.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import Field
from readback_core.model import StrictModel

Family = Literal["lookup", "comparison", "trend", "top_k", "definition", "multi", "refusal"]
FAMILIES: tuple[Family, ...] = ("lookup", "comparison", "trend", "top_k", "definition", "multi", "refusal")
Split = Literal["dev", "test"]


class KnownClaim(StrictModel):
    value: float
    unit: str
    fmt: str
    tolerance: float
    sql: str | None = None
    manifest_key: str | None = None
    label: str


class Question(StrictModel):
    id: str
    family: Family
    warehouses: list[str]
    question: str
    claims: list[KnownClaim] = Field(default_factory=list)
    entity: str | None = None
    direction: Literal["rose", "fell", "unchanged"] | None = None
    ranking: list[str] = Field(default_factory=list)
    key_phrases: list[str] = Field(default_factory=list)
    refuse: bool = False
    measure: str | None = None
    entities: list[str] = Field(default_factory=list)
    split: Split


def load(folder: Path) -> list[Question]:
    out: list[Question] = []
    for path in sorted(folder.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        out.extend(Question.model_validate(q) for q in data["questions"])
    ids = [q.id for q in out]
    if len(ids) != len(set(ids)):
        raise ValueError("golden question ids repeat")
    return sorted(out, key=lambda q: q.id)


def by_split(questions: list[Question], split: Split) -> list[Question]:
    return [q for q in questions if q.split == split]
