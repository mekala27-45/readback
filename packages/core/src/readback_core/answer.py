"""The answer: what the agent drafts, and what it ships after the gate.

A Draft is what a model (or the floor) produces: prose, and one claim per number in the prose, each
pointing at its evidence. The Answer is the Draft after the gate, with every claim's span in the text,
its readback verdict, and the run's provenance (provider, model, tokens, latency, trace id). The chat
renders a chip over each claim span. The same models are the structured output schema a provider is
asked for, so there is one definition.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from readback_core.statements import STATEMENT

Verdict = Literal["verified", "repaired", "refused"]


class DraftClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: float = Field(description="the number as it appears in the text, in the unit given")
    unit: str = Field(description="percent, fraction, dollars, count, minutes, ratio, years, none ...")
    display: str = Field(description="the number exactly as written in the text, e.g. 40.4% or $329,620")
    warehouse: Literal["doorstep", "turnaround", "ledger"] | None = None
    result_id: str | None = None
    column: str | None = None
    row: int = 0
    evidence_unit: str | None = Field(default=None, description="the unit of a computed result column")
    manifest_key: str | None = None
    catalog_key: str | None = None
    definition_id: str | None = None
    sql: str | None = None


class Choice(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: str
    name: str
    candidates: list[str]


class Draft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str
    claims: list[DraftClaim] = Field(default_factory=list)
    warehouses: list[str] = Field(default_factory=list)
    selection: list[str] = Field(default_factory=list, description="the entities the answer picks, in order")
    direction: Literal["rose", "fell", "unchanged"] | None = None
    refused: bool = False
    refusal_reason: str | None = None


class ShippedClaim(DraftClaim):
    span: tuple[int, int] | None = None
    verdict: str = "unchecked"
    evidence: float | None = None
    tolerance: float | None = None
    reason: str = ""


class GateSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tokens: int = 0
    exempt: int = 0
    unsupported_before: int = 0
    unsupported_after: int = 0
    readback_calls: int = 0
    caught: list[str] = Field(default_factory=list, description="what the gate caught on the first draft")
    first_draft: str | None = None


class Answer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str | None = None
    question: str
    family: str
    text: str
    claims: list[ShippedClaim] = Field(default_factory=list)
    warehouses: list[str] = Field(default_factory=list)
    selection: list[str] = Field(default_factory=list)
    direction: Literal["rose", "fell", "unchanged"] | None = None
    verdict: Verdict
    refusal_reason: str | None = None
    provider: str
    model: str
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: float = 0.0
    tool_calls: int = 0
    model_calls: int = 0
    tools_called: list[str] = Field(default_factory=list)
    trace_id: str = ""
    prompt_hash: str = ""
    gate: GateSummary = Field(default_factory=GateSummary)
    statement: str = STATEMENT
