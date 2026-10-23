"""Alembic for the readback schema. The version table lives in the schema itself, the Day 13
pattern, so the builds that share the Neon project never see each other's migrations."""

from __future__ import annotations

import sqlalchemy as sa
from readback_api import db
from readback_providers import ledger

from alembic import context

target_metadata = [db.metadata, ledger.metadata]


def run() -> None:
    engine = db.engine()
    with engine.connect() as conn:
        if conn.dialect.name == "postgresql":
            conn.execute(sa.text(f'create schema if not exists "{db.SCHEMA}"'))
            conn.commit()
        context.configure(
            connection=conn,
            target_metadata=target_metadata,
            version_table_schema=db.SCHEMA if conn.dialect.name == "postgresql" else None,
        )
        with context.begin_transaction():
            context.run_migrations()


run()
