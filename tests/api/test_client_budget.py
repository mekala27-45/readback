from __future__ import annotations

import datetime as dt

import pytest
from readback_api.client_budget import ClientBudget, MemoryCounter, client_key


def test_the_hourly_cap_refuses_the_sixty_first_request() -> None:
    now = dt.datetime(2026, 10, 23, 14, 5, tzinfo=dt.UTC)
    b = ClientBudget(MemoryCounter(), clock=lambda: now)
    decisions = [b.check("203.0.113.9") for _ in range(61)]
    assert all(d.allowed for d in decisions[:60])
    assert not decisions[60].allowed and "60 requests for the hour" in decisions[60].message


def test_the_daily_cap_refuses_past_six_hundred_across_hours() -> None:
    clock = {"t": dt.datetime(2026, 10, 23, 0, 0, tzinfo=dt.UTC)}
    b = ClientBudget(MemoryCounter(), hourly=10_000, clock=lambda: clock["t"])
    results = [b.check("198.51.100.1") for _ in range(601)]
    assert results[599].allowed and not results[600].allowed


def test_clients_are_counted_apart_and_never_stored_by_address() -> None:
    b = ClientBudget(MemoryCounter(), hourly=1)
    assert b.check("a").allowed and b.check("b").allowed and not b.check("a").allowed
    assert "198.51" not in client_key("198.51.100.1") and len(client_key("x")) == 32


def test_a_neon_pooled_string_becomes_direct(monkeypatch: pytest.MonkeyPatch) -> None:
    from readback_api import db

    pooled = "postgresql://u:p@ep-orange-tree-b7-pooler.c-13.us-east-1.aws.neon.tech/neondb?sslmode=require"
    monkeypatch.setenv("DATABASE_URL", pooled)
    assert db.database_url() == (
        "postgresql+psycopg://u:p@ep-orange-tree-b7.c-13.us-east-1.aws.neon.tech/neondb?sslmode=require"
    )
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@db.example.com:5432/x")
    assert db.database_url() == "postgresql+psycopg://u:p@db.example.com:5432/x"
