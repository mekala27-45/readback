"""The SQL guard: every refusal names its clause; the limit is rewritten; a clean SELECT runs."""

from __future__ import annotations

import pytest

from readback_warehouse.connection import Warehouse
from readback_warehouse.guard import ROW_CEILING, Refused, guard
from readback_warehouse.run import TimedOut, execute

TABLES = ["mart_metro_year", "ch5_ranking", "grain_loans", "ch1_national_series"]


@pytest.mark.parametrize(
    ("sql", "clause"),
    [
        ("insert into mart_metro_year values (1)", "INSERT"),
        ("update mart_metro_year set year = 1", "UPDATE"),
        ("delete from mart_metro_year", "DELETE"),
        ("create table x as select 1", "CREATE"),
        ("drop view mart_metro_year", "DROP"),
        ("select 1; select 2", "a second statement"),
        ("select 1; drop table x", "a second statement"),
        ("select 1 /* hide */; drop table x -- trailing", "a second statement"),
        ("attach 'x.db'", "ATTACH"),
        ("copy mart_metro_year to 'x.csv'", "COPY"),
        ("install httpfs", "INSTALL"),
        ("load httpfs", "a command"),
        ("pragma version", "PRAGMA"),
        ("set threads = 1", "SET"),
        ("select * from read_parquet('x.parquet')", "the function read_parquet"),
        ("select getenv('HOME')", "the function getenv"),
        ("select * from turnaround.mart_carrier_month", "the reference turnaround.mart_carrier_month"),
        ("select * from not_a_table", "the table not_a_table"),
        ("with w as (delete from mart_metro_year returning *) select * from w", "DELETE"),
        ("", "the statement"),
    ],
)
def test_refusals_name_the_clause(sql: str, clause: str) -> None:
    with pytest.raises(Refused) as err:
        guard(sql, "doorstep", TABLES)
    assert err.value.clause == clause


def test_limit_is_added_at_the_ceiling_and_capped() -> None:
    assert guard("select * from ch5_ranking", "doorstep", TABLES).limit == ROW_CEILING
    assert guard("select * from ch5_ranking limit 9999", "doorstep", TABLES).sql.endswith(f"LIMIT {ROW_CEILING}")
    assert guard("select * from ch5_ranking limit 3", "doorstep", TABLES).limit == 3
    assert guard("select * from ch5_ranking", "doorstep", TABLES, limit=7).limit == 7


def test_unqualified_names_are_qualified_and_ctes_are_left_alone() -> None:
    g = guard("with a as (select year from ch1_national_series) select * from a", "doorstep", TABLES)
    assert "doorstep.ch1_national_series" in g.sql and "doorstep.a" not in g.sql


def test_a_clean_select_runs_and_counts_before_the_limit() -> None:
    w = Warehouse.shared()
    g = guard("select cbsa_title from ch5_ranking order by cbsa_title", "doorstep", TABLES, limit=5)
    r = execute(w, g)
    assert len(r.rows) == 5 and r.row_count == 382


def test_a_statement_past_the_timeout_is_stopped() -> None:
    w = Warehouse.shared()
    g = guard("select count(*) from grain_loans a, grain_loans b", "doorstep", TABLES)
    with pytest.raises(TimedOut):
        execute(w, g, timeout=0.5)


def test_the_connection_refuses_a_write_the_guard_never_sees() -> None:
    w = Warehouse.shared()
    with pytest.raises(Exception, match="(?i)read.only|cannot execute"):
        w.query("create table doorstep.x as select 1")
