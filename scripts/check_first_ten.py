"""Step three's hand check: ten development questions answered by SQL written by hand.

Each SQL below was written against the real marts without the measures table, from a different
table or by recomputing from components where one exists, so it checks the generator rather than
repeating it. The result is written to results/golden_first_ten.json and the test asserts it.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from readback_evals.golden import load
from readback_warehouse.connection import Warehouse

# question id -> (claim index, hand written SQL, what it checks)
HAND = {
    "D-lookup-04": (
        0,
        "select value_anchored / median_income from doorstep.fct_metro_year "
        "where cbsa_code = '33460' and year = 2016",
        "price to income recomputed from its two components, in the fact table rather than the mart",
    ),
    "D-lookup-06": (
        0,
        "select renter_households from doorstep.fct_metro_year where cbsa_code = '12420' and year = 2009",
        "the count by CBSA code in the fact table",
    ),
    "D-comparison-08": (
        0,
        "select renter_burdened_share from doorstep.ch3_national_bands where year = 2006",
        "the national burden from chapter 3's table, not the national mart",
    ),
    "D-trend-03": (
        0,
        "select median_income from doorstep.fct_metro_year where cbsa_code = '40900' and year = 2013",
        "the income by CBSA code in the fact table",
    ),
    "T-lookup-01": (
        0,
        "select sum(on_time) / sum(flown) from turnaround.mart_carrier_day "
        "where carrier = 'NK' and year(flight_date) = 2018",
        "the on time rate from the daily mart rather than the monthly one",
    ),
    "T-lookup-04": (
        0,
        "select sum(flown) from turnaround.mart_carrier_day "
        "where carrier = 'AA' and year(flight_date) = 2015",
        "flights flown from the daily mart",
    ),
    "T-lookup-07": (
        0,
        'select "On time" from turnaround.export_ch1_by_year where "Year" = 2019',
        "the national on time rate as chapter 1 published it",
    ),
    "L-lookup-04": (
        0,
        "select sum(net_income) from ledger.metrics_bank_month "
        "where period in ('2024-04', '2024-05', '2024-06')",
        "quarterly net income summed from the three months",
    ),
    "L-lookup-06": (
        0,
        "select nonperforming_loans / total_loans from ledger.metrics_bank_quarter where period = '2026Q2'",
        "the nonperforming ratio recomputed from its components",
    ),
    "L-topk-07": (
        0,
        "select alerts from ledger.models_aml_triage_rule_scorecard where rule = 'structuring'",
        "the alert count from the model registry's copy of the scorecard",
    ),
}


def run() -> list[dict[str, object]]:
    w = Warehouse.shared()
    golden = {q.id: q for q in load(ROOT / "evals" / "golden")}
    out = []
    for qid, (i, sql, what) in sorted(HAND.items()):
        q = golden[qid]
        if q.split != "dev":
            raise SystemExit(f"{qid} is not a development question; the hand check reads development only")
        known = q.claims[i]
        hand = float(w.scalar(sql))
        out.append(
            {
                "id": qid,
                "question": q.question,
                "known": known.value,
                "hand": hand,
                "difference": abs(hand - known.value),
                "tolerance": known.tolerance,
                "agrees": abs(hand - known.value) <= known.tolerance,
                "sql": sql,
                "checks": what,
            }
        )
    return out


if __name__ == "__main__":
    rows = run()
    path = ROOT / "results" / "golden_first_ten.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=1) + "\n", encoding="utf-8")
    for r in rows:
        print(
            f"{r['id']}: known {r['known']:.6g}, hand {r['hand']:.6g}, "
            f"{'agrees' if r['agrees'] else 'DISAGREES'}"
        )
    sys.exit(0 if all(r["agrees"] for r in rows) else 1)
