"""The router: the first eligible provider, with the reason recorded.

Eligible means the key is present, the day's budget has room, and the provider was not called at its
per minute cap in the last minute. The floor is always eligible and always last. The router never
pools: an answer is one provider, one model, one prompt registry hash.
"""

from __future__ import annotations

from dataclasses import dataclass

from readback_providers.ledger import Ledger
from readback_providers.registry import Provider


@dataclass(frozen=True)
class Choice:
    provider: Provider
    reason: str
    skipped: tuple[tuple[str, str], ...]


class Router:
    def __init__(self, providers: list[Provider], ledger: Ledger, only: str | None = None) -> None:
        self.providers = providers
        self.ledger = ledger
        self.only = only

    def eligibility(self, p: Provider) -> str | None:
        """None when eligible, else why not."""
        if p.is_floor:
            return None
        if not p.has_key():
            return f"no key in {p.key_env}"
        if p.daily_budget is not None and self.ledger.remaining(p.name, p.daily_budget) == 0:
            return "the day's budget is spent"
        if p.per_minute is not None and self.ledger.last_minute(p.name) >= p.per_minute:
            return "at its per minute cap"
        return None

    def choose(self, exclude: tuple[str, ...] = ()) -> Choice:
        skipped: list[tuple[str, str]] = []
        for p in self.providers:
            if self.only and p.name != self.only and not p.is_floor:
                continue
            if p.name in exclude:
                skipped.append((p.name, "excluded after a refusal at the cap"))
                continue
            why = self.eligibility(p)
            if why is None:
                reason = "the floor: no model" if p.is_floor else "first eligible provider"
                return Choice(p, reason, tuple(skipped))
            skipped.append((p.name, why))
        raise RuntimeError("the registry has no floor")  # load() makes this unreachable

    def status(self) -> list[dict[str, object]]:
        return [
            {
                "provider": p.name,
                "model": p.model_id(),
                "eligible": self.eligibility(p) is None,
                "reason": self.eligibility(p) or "eligible",
                "used_today": 0 if p.is_floor else self.ledger.used(p.name),
                "daily_budget": p.daily_budget,
            }
            for p in self.providers
        ]
