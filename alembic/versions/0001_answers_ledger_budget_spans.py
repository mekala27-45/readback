"""The answer log, the provider ledger, the client budget and the spans."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0001"
down_revision = None


def upgrade() -> None:
    op.create_table(
        "answers",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("thread_id", sa.String(64), nullable=False, index=True),
        sa.Column("question", sa.Text, nullable=False),
        sa.Column("answer", sa.Text, nullable=False),
        sa.Column("verdict", sa.String(16), nullable=False),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("model", sa.String(120), nullable=False),
        sa.Column("tokens_in", sa.Integer, nullable=False),
        sa.Column("tokens_out", sa.Integer, nullable=False),
        sa.Column("latency_ms", sa.Float, nullable=False),
        sa.Column("trace_id", sa.String(32), nullable=False, index=True),
        sa.Column("demo", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "spans",
        sa.Column("span_id", sa.String(16), primary_key=True),
        sa.Column("trace_id", sa.String(32), nullable=False, index=True),
        sa.Column("parent_id", sa.String(16)),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("start_ns", sa.BigInteger, nullable=False),
        sa.Column("end_ns", sa.BigInteger, nullable=False),
        sa.Column("attributes", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "client_budget",
        sa.Column("client", sa.String(32), primary_key=True),
        sa.Column("window_kind", sa.String(8), primary_key=True),
        sa.Column("window_start", sa.DateTime(timezone=True), primary_key=True),
        sa.Column("used", sa.Integer, nullable=False),
    )
    op.create_table(
        "provider_budget",
        sa.Column("provider", sa.String(40), primary_key=True),
        sa.Column("day", sa.Date, primary_key=True),
        sa.Column("used", sa.Integer, nullable=False),
    )
    op.create_table(
        "model_calls",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("model", sa.String(120), nullable=False),
        sa.Column("digest", sa.String(64), nullable=False),
        sa.Column("trace_id", sa.String(32), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    for name in ("model_calls", "provider_budget", "client_budget", "spans", "answers"):
        op.drop_table(name)
