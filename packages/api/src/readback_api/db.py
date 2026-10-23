"""The answer log, the spans and the client budget, in Postgres (schema readback) or SQLite.

Neon Postgres in production, in the readback schema of the project the earlier builds share; a
SQLite file when DATABASE_URL is unset, so the API runs on a laptop and in tests with the same code.
The provider ledger's two tables (provider_budget, model_calls) live beside these, created from the
ledger's own metadata. Alembic owns the schema in production (alembic/versions); create_all is the
local path only.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import sqlalchemy as sa

SCHEMA = os.environ.get("READBACK_DB_SCHEMA", "readback")
metadata = sa.MetaData()
answers = sa.Table(
    "answers",
    metadata,
    sa.Column("id", sa.String(32), primary_key=True),
    sa.Column("thread_id", sa.String(64), nullable=False, index=True),
    sa.Column("question", sa.Text, nullable=False),  # redacted before it gets here
    sa.Column("answer", sa.Text, nullable=False),  # the Answer object as JSON
    sa.Column("verdict", sa.String(16), nullable=False),
    sa.Column("provider", sa.String(40), nullable=False),
    sa.Column("model", sa.String(120), nullable=False),
    sa.Column("tokens_in", sa.Integer, nullable=False),
    sa.Column("tokens_out", sa.Integer, nullable=False),
    sa.Column("latency_ms", sa.Float, nullable=False),
    sa.Column("trace_id", sa.String(32), nullable=False, index=True),
    sa.Column("demo", sa.Boolean, nullable=False, default=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)
spans = sa.Table(
    "spans",
    metadata,
    sa.Column("span_id", sa.String(16), primary_key=True),
    sa.Column("trace_id", sa.String(32), nullable=False, index=True),
    sa.Column("parent_id", sa.String(16)),
    sa.Column("name", sa.String(200), nullable=False),
    sa.Column("start_ns", sa.BigInteger, nullable=False),
    sa.Column("end_ns", sa.BigInteger, nullable=False),
    sa.Column("attributes", sa.Text, nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)
client_budget = sa.Table(
    "client_budget",
    metadata,
    sa.Column("client", sa.String(32), primary_key=True),
    sa.Column("window_kind", sa.String(8), primary_key=True),
    sa.Column("window_start", sa.DateTime(timezone=True), primary_key=True),
    sa.Column("used", sa.Integer, nullable=False),
)
SPAN_RETENTION = dt.timedelta(days=7)


def database_url() -> str:
    url = os.environ.get("DATABASE_URL", "").strip()
    if url:
        if url.startswith("postgres://"):
            url = "postgresql+psycopg://" + url[len("postgres://") :]
        elif url.startswith("postgresql://"):
            url = "postgresql+psycopg://" + url[len("postgresql://") :]
        return url
    path = Path(os.environ.get("READBACK_SQLITE", Path(tempfile.gettempdir()) / "readback.sqlite"))
    return f"sqlite+pysqlite:///{path}"


def engine(url: str | None = None) -> sa.Engine:
    url = url or database_url()
    if url.startswith("postgresql"):
        eng = sa.create_engine(url, pool_pre_ping=True, pool_size=2, max_overflow=2, pool_recycle=240,
                               connect_args={"options": f"-csearch_path={SCHEMA}"})
    else:
        eng = sa.create_engine(url, connect_args={"check_same_thread": False})
    return eng


def create_local(eng: sa.Engine) -> None:
    """The local and test path. Production runs alembic upgrade head instead."""
    from readback_providers import ledger

    if eng.dialect.name == "postgresql":
        with eng.begin() as conn:
            conn.execute(sa.text(f'create schema if not exists "{SCHEMA}"'))
    metadata.create_all(eng)
    ledger.metadata.create_all(eng)


@dataclass
class Log:
    engine: sa.Engine

    def write_answer(self, answer_id: str, thread_id: str, answer: dict[str, Any], demo: bool = False) -> None:
        with self.engine.begin() as conn:
            conn.execute(answers.insert().values(
                id=answer_id, thread_id=thread_id, question=answer["question"], answer=json.dumps(answer, sort_keys=True),
                verdict=answer["verdict"], provider=answer["provider"], model=answer["model"],
                tokens_in=int(answer.get("tokens_in", 0)), tokens_out=int(answer.get("tokens_out", 0)),
                latency_ms=float(answer.get("latency_ms", 0.0)), trace_id=answer.get("trace_id", ""), demo=demo,
                created_at=dt.datetime.now(dt.UTC),
            ))

    def read_answer(self, answer_id: str) -> dict[str, Any] | None:
        with self.engine.connect() as conn:
            row = conn.execute(sa.select(answers).where(answers.c.id == answer_id)).mappings().first()
        if row is None:
            return None
        body: dict[str, Any] = json.loads(row["answer"])
        body["id"] = row["id"]
        return body

    def recent(self, limit: int = 20, demo: bool | None = None) -> list[dict[str, Any]]:
        q = sa.select(answers.c.id, answers.c.question, answers.c.verdict, answers.c.provider, answers.c.trace_id, answers.c.created_at)
        if demo is not None:
            q = q.where(answers.c.demo == demo)
        q = q.order_by(answers.c.created_at.desc()).limit(max(1, min(limit, 100)))
        with self.engine.connect() as conn:
            return [dict(r, created_at=r["created_at"].isoformat()) for r in conn.execute(q).mappings()]

    def write_spans(self, rows: list[dict[str, Any]]) -> int:
        if not rows:
            return 0
        now = dt.datetime.now(dt.UTC)
        with self.engine.begin() as conn:
            conn.execute(spans.delete().where(spans.c.created_at < now - SPAN_RETENTION))
            existing = {r[0] for r in conn.execute(sa.select(spans.c.span_id).where(spans.c.span_id.in_([r["span_id"] for r in rows])))}
            fresh = [r for r in rows if r["span_id"] not in existing]
            if fresh:
                conn.execute(spans.insert(), [
                    {"span_id": r["span_id"], "trace_id": r["trace_id"], "parent_id": r["parent_id"], "name": r["name"],
                     "start_ns": r["start_ns"], "end_ns": r["end_ns"], "attributes": json.dumps(r["attributes"], sort_keys=True), "created_at": now}
                    for r in fresh
                ])
        return len(fresh)

    def spans_of(self, trace_id: str) -> list[dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(sa.select(spans).where(spans.c.trace_id == trace_id).order_by(spans.c.start_ns)).mappings()
            return [dict(r, attributes=json.loads(r["attributes"]), created_at=r["created_at"].isoformat()) for r in rows]

    def clear_answers(self) -> int:
        with self.engine.begin() as conn:
            return int(conn.execute(answers.delete()).rowcount or 0)


class SqlCounter:
    """The client budget's counter over the client_budget table: one upsert that returns the count."""

    def __init__(self, eng: sa.Engine) -> None:
        self.engine = eng

    def increment(self, client: str, window: str, start: dt.datetime) -> int:
        if self.engine.dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import insert
        else:
            from sqlalchemy.dialects.sqlite import insert
        stmt = insert(client_budget).values(client=client, window_kind=window, window_start=start, used=1)
        stmt = stmt.on_conflict_do_update(index_elements=["client", "window_kind", "window_start"],
                                          set_={"used": client_budget.c.used + 1}).returning(client_budget.c.used)
        with self.engine.begin() as conn:
            return int(conn.execute(stmt).scalar_one())
