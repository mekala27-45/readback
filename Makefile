# readback. Every target is a step a person or the CI runs; `make help` lists them.
PY := uv run python
R := uv run readback

.PHONY: help setup fetch catalog golden check-data gates lint types test cov render check-render web serve-mcp \
        eval scorecard manifest probe rederive live-check load-test demo clean

help:
	@grep -E '^[a-z-]+:' Makefile | sed 's/:.*//' | sort | tr '\n' ' '; echo

setup:
	uv sync --frozen

fetch:
	$(PY) scripts/fetch_warehouses.py

catalog: fetch
	$(PY) scripts/build_catalog.py

golden:
	$(PY) scripts/build_golden.py

gates:
	$(PY) scripts/check_no_em_dash.py
	$(PY) scripts/check_vocabulary.py
	$(PY) scripts/check_statement.py
	$(PY) scripts/scan_for_planted_identifiers.py
	node scripts/validate_palette.js --config web/src/theme/palette.json

lint:
	uv run ruff check .
	uv run ruff format --check .

types:
	uv run mypy

test:
	uv run pytest

cov:
	uv run pytest --cov --cov-report=term

manifest:
	$(R) manifest

render:
	$(PY) scripts/check_published_numbers.py --write

check-render:
	$(PY) scripts/check_published_numbers.py

eval:
	$(R) eval --split dev
	$(R) eval --split test

scorecard:
	$(R) scorecard

serve-mcp:
	uv run readback-mcp

probe:
	$(PY) scripts/probe_hosts.py

rederive:
	$(PY) scripts/reset_and_rederive.py

live-check:
	$(PY) scripts/live_check.py

load-test:
	$(PY) scripts/load_test.py

web:
	cd web && npm ci && npm run build

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache web/out web/.next
