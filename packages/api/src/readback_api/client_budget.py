"""The free tier's protection: 60 requests an hour and 600 a day per client, kept in Postgres.

A client is a SHA-256 of its address with a salt, never the address itself. The count is taken and
checked in one statement (an upsert that returns the new count), so two requests at the same moment
cannot both slip under the cap. Past the cap the request is refused with a message saying when the
window resets. The read only server needs no token; this is the whole of its protection, together
with the ceilings on rows, time and k.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import os
import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

HOURLY = 60
DAILY = 600


@dataclass(frozen=True)
class Decision:
    allowed: bool
    hour_used: int
    day_used: int
    message: str


def client_key(address: str) -> str:
    salt = os.environ.get("READBACK_CLIENT_SALT", "readback")
    return hashlib.sha256(f"{salt}:{address}".encode()).hexdigest()[:32]


class Counter(Protocol):
    def increment(self, client: str, window: str, start: dt.datetime) -> int: ...


class MemoryCounter:
    """For stdio, tests and a host with no database."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counts: dict[tuple[str, str, str], int] = {}

    def increment(self, client: str, window: str, start: dt.datetime) -> int:
        key = (client, window, start.isoformat())
        with self._lock:
            self._counts[key] = self._counts.get(key, 0) + 1
            return self._counts[key]


class PostgresCounter:
    SQL = (
        "insert into readback.client_budget (client, window_kind, window_start, used) values (%s, %s, %s, 1) "
        "on conflict (client, window_kind, window_start) "
        "do update set used = readback.client_budget.used + 1 "
        "returning used"
    )

    def __init__(self, connect: Callable[[], object]) -> None:
        self.connect = connect

    def increment(self, client: str, window: str, start: dt.datetime) -> int:
        conn = self.connect()
        with conn:  # type: ignore[attr-defined]
            row = conn.execute(self.SQL, (client, window, start)).fetchone()  # type: ignore[attr-defined]
        return int(row[0])


class ClientBudget:
    def __init__(
        self,
        counter: Counter,
        hourly: int = HOURLY,
        daily: int = DAILY,
        clock: Callable[[], dt.datetime] | None = None,
    ) -> None:
        self.counter = counter
        self.hourly = hourly
        self.daily = daily
        self.clock = clock or (lambda: dt.datetime.now(dt.UTC))

    def check(self, address: str) -> Decision:
        now = self.clock()
        client = client_key(address)
        hour = now.replace(minute=0, second=0, microsecond=0)
        day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        h = self.counter.increment(client, "hour", hour)
        d = self.counter.increment(client, "day", day)
        if h > self.hourly:
            return Decision(
                False,
                h,
                d,
                f"this client has used its {self.hourly} requests for the hour; "
                f"the window resets at {(hour + dt.timedelta(hours=1)):%H:%M} UTC",
            )
        if d > self.daily:
            return Decision(
                False,
                h,
                d,
                f"this client has used its {self.daily} requests for the day; "
                "the window resets at midnight UTC",
            )
        return Decision(True, h, d, "")
