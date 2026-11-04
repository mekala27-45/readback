"""Exercise the fourth warehouse through discovery, guarded SQL and numeric readback."""

from __future__ import annotations

import csv
import json
from decimal import Decimal

from readback_core import paths, warehouse_lock
from readback_mcp_server import tools
from readback_mcp_server.schemas import Claim
from readback_mcp_server.state import State


def main() -> None:
    state = State()
    discovered = tools.warehouses(state)
    assert {w.name for w in discovered.warehouses} == {"doorstep", "ledger", "turnaround", "mlspend"}
    table = tools.describe(state, "mlspend", "showback")
    assert table.grain == ["month", "team", "method"]
    assert tools.search_catalog(state, "mlspend showback cost", warehouse="mlspend").hits
    sql = "SELECT SUM(cost_usd) AS cost_usd FROM showback WHERE method = 'usage'"
    result = tools.run_sql(state, "mlspend", sql, None, "mlspend-integration")
    source = paths.warehouses_dir() / "mlspend/exports/readback/showback.csv"
    with source.open(encoding="utf-8", newline="") as stream:
        expected = sum(
            (Decimal(r["cost_usd"]) for r in csv.DictReader(stream) if r["method"] == "usage"), Decimal(0)
        )
    assert abs(Decimal(str(result.rows[0][0])) - expected) < Decimal("0.000001")
    claim = Claim(
        value=float(expected),
        unit="dollars",
        warehouse="mlspend",
        result_id=result.result_id,
        column="cost_usd",
    )
    assert tools.readback(state, claim, "mlspend-integration").verdict == "agree"
    claim.value += 100
    assert tools.readback(state, claim, "mlspend-integration").verdict == "disagree"
    for forbidden in ("DROP TABLE showback", "SELECT * FROM read_csv('/etc/passwd')"):
        try:
            tools.run_sql(state, "mlspend", forbidden, None, "mlspend-integration")
        except tools.ToolRefusal:
            pass
        else:
            raise AssertionError("SQL guard accepted a forbidden query")
    for forbidden in ("CREATE TABLE mlspend.no_write AS SELECT 1", "SELECT * FROM read_csv('/etc/passwd')"):
        try:
            state.warehouse.query(forbidden)
        except Exception:
            pass
        else:
            raise AssertionError("Read-only connection accepted a forbidden query")
    print(
        json.dumps(
            {
                "status": "pass",
                "source_commit": warehouse_lock.load()["warehouses"]["mlspend"]["commit"],
                "rows": table.rows,
                "usage_total_usd": str(expected),
                "readback": "agree",
                "changed_claim": "disagree",
                "guard_and_connection": "refused",
            }
        )
    )


if __name__ == "__main__":
    main()
