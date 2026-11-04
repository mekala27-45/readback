# MLSpend warehouse

MLSpend can be loaded alongside the released portfolio warehouses. Its showback table contains simulated platform cost, with one row per team, month and allocation policy. Choose one method before summing dollars; policies are alternatives. These are not paid invoices.

The source is pinned in `data/mlspend.source.json`. Check out that exact MLSpend commit, then run:

```sh
uv run python scripts/add_mlspend.py --source /path/to/mlspend --commit "$MLSPEND_COMMIT"
export READBACK_WAREHOUSE_LOCK=data/warehouses.mlspend.lock.json
uv run python scripts/fetch_warehouses.py
uv run python scripts/build_catalog.py
uv run python scripts/check_mlspend.py
uv run readback-mcp
```

The installer verifies the checkout and committed bytes, then generates a separate combined lock. The catalog builder checks the hashes, column types, row count and unique grain. Discovery, catalog search, describe, guarded SQL and numeric readback support the new table. External metric SQL is not executed during catalog construction. The deterministic natural-language floor retains its registered question families; new showback questions use the MCP tools directly or a tool-calling client.

The original warehouse lock, released catalogs, golden questions, prompts and evaluation claims remain the default. Use a separate checkout for the combined catalog. The integration job checks an independent decimal total, agreement with numeric readback, disagreement for an altered claim, and refusal of writes and unlisted files.

> Answers are drawn from the published tables of three portfolio builds by Ajay Mekala: doorstep (public housing data from FHFA, the Census Bureau, HUD, the CFPB and Freddie Mac), turnaround (public flight data from the Bureau of Transportation Statistics, the FAA and OurAirports, with weather from Open-Meteo under CC BY 4.0) and ledger (a fictional bank, Harborline, with public HMDA, CFPB, FDIC and macro series). No person appears in any table, and questions are redacted before a model sees them. Every number is read back to the warehouse before it is shown. This is a portfolio demonstration, not financial, travel or lending advice.


