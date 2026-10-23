"""The readback command: eval, redteam, scorecard, manifest.

uv run readback eval --provider floor
uv run readback redteam --provider floor
uv run readback scorecard
uv run readback manifest
"""

from __future__ import annotations

import asyncio
import json

import typer

app = typer.Typer(add_completion=False, no_args_is_help=True)


@app.command()
def eval(provider: str = "floor", split: str = "all") -> None:
    """Run the golden set through one provider and grade it."""
    from readback_core import paths

    from readback_evals.golden import load
    from readback_evals.runner import run_golden

    questions = load(paths.evals_dir() / "golden")
    if split != "all":
        questions = [q for q in questions if q.split == split]
    doc = asyncio.run(run_golden(provider, questions))
    rows = doc["rows"]
    graded = [r for r in rows if r["graded"]]
    print(
        json.dumps(
            {
                "provider": provider,
                "questions": len(rows),
                "graded": len(graded),
                "passed": sum(r["passed"] for r in graded),
            }
        )
    )


@app.command()
def redteam(provider: str = "floor") -> None:
    """Run the 15 injection cases through one provider."""
    from readback_evals.runner import run_redteam

    out = asyncio.run(run_redteam(provider))
    print(json.dumps({"provider": provider, "graded": out["graded"], "passed": out["passed"]}))


@app.command()
def scorecard() -> None:
    """Build results/evals/scorecard.json from the runs on disk."""
    from readback_evals.scorecard import build, write

    card = build()
    write(card)
    print(
        json.dumps(
            {"providers": [r["provider"] for r in card["test"]["rows"]], "default": card["default_provider"]}
        )
    )


@app.command()
def manifest() -> None:
    """Assemble results/manifest.json from every result on disk."""
    from readback_evals.publish import assemble

    m = assemble()
    print(json.dumps({"values": len(m.values), "tables": len(m.tables), "figures": len(m.figures)}))


if __name__ == "__main__":
    app()
