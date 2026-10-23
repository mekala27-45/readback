"""The budget ledger: requests per provider per day, counted before the call, in the same
transaction as the audit row of that call.

The day is the Pacific day, because the Gemini free quota resets at midnight Pacific. A call reserves
its slot first: the day's count is incremented and the audit row written in one transaction, and if
the count passes the cap the transaction rolls back and the router moves to the next provider. A
crash between the reservation and the call leaves a counted call, never an uncounted one. Postgres
in production (schema readback); SQLite in tests and on a laptop, through the same SQLAlchemy core.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from zoneinfo import ZoneInfo

import sqlalchemy as sa

PACIFIC = ZoneInfo("America/Los_Angeles")
metadata = sa.MetaData()
budget = sa.Table(
    "provider_budget",
    metadata,
    sa.Column("provider", sa.String(40), primary_key=True),
    sa.Column("day", sa.Date, primary_key=True),
    sa.Column("used", sa.Integer, nullable=False),
)
calls = sa.Table(
    "model_calls",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("provider", sa.String(40), nullable=False),
    sa.Column("model", sa.String(120), nullable=False),
    sa.Column("digest", sa.String(64), nullable=False),
    sa.Column("trace_id", sa.String(32), nullable=False),
    sa.Column("at", sa.DateTime(timezone=True), nullable=False),
)


class BudgetSpent(RuntimeError):
    def __init__(self, provider: str, cap: int) -> None:
        super().__init__(f"{provider} has used its {cap} requests for the Pacific day")
        self.provider = provider


def pacific_day(now: dt.datetime) -> dt.date:
    return now.astimezone(PACIFIC).date()


class Ledger:
    def __init__(self, engine: sa.Engine, clock: Callable[[], dt.datetime] | None = None) -> None:
        self.engine = engine
        self.clock = clock or (lambda: dt.datetime.now(dt.UTC))
        metadata.create_all(engine)

    @classmethod
    def memory(cls, clock: Callable[[], dt.datetime] | None = None) -> Ledger:
        return cls(sa.create_engine("sqlite+pysqlite:///:memory:"), clock)

    def used(self, provider: str) -> int:
        day = pacific_day(self.clock())
        with self.engine.connect() as conn:
            value = conn.execute(sa.select(budget.c.used).where(budget.c.provider == provider, budget.c.day == day)).scalar()
        return int(value or 0)

    def remaining(self, provider: str, cap: int | None) -> int | None:
        return None if cap is None else max(0, cap - self.used(provider))

    def last_minute(self, provider: str) -> int:
        since = self.clock() - dt.timedelta(minutes=1)
        with self.engine.connect() as conn:
            value = conn.execute(sa.select(sa.func.count()).select_from(calls).where(calls.c.provider == provider, calls.c.at > since)).scalar()
        return int(value or 0)

    def reserve(self, provider: str, model: str, cap: int, digest: str, trace_id: str,
                fail_between: Callable[[], None] | None = None) -> int:
        """Count the call and write its audit row together; refuse past the cap. Returns the new count."""
        now = self.clock()
        day = pacific_day(now)
        with self.engine.begin() as conn:
            # One upsert that returns the new count, so two calls at once cannot both pass the cap.
            if self.engine.dialect.name == "postgresql":
                from sqlalchemy.dialects.postgresql import insert
            else:
                from sqlalchemy.dialects.sqlite import insert
            stmt = insert(budget).values(provider=provider, day=day, used=1)
            stmt = stmt.on_conflict_do_update(index_elements=["provider", "day"], set_={"used": budget.c.used + 1}).returning(budget.c.used)
            used = int(conn.execute(stmt).scalar_one())
            if used > cap:
                raise BudgetSpent(provider, cap)  # the raise rolls the increment back
            if fail_between is not None:
                fail_between()
            conn.execute(calls.insert().values(provider=provider, model=model, digest=digest, trace_id=trace_id, at=now))
        return used

    def audit_rows(self) -> int:
        with self.engine.connect() as conn:
            return int(conn.execute(sa.select(sa.func.count()).select_from(calls)).scalar() or 0)
