"""The interior test of retrieval depth: the floor's definition answers at k of 3, 5 and 8.

Only the definition family reads search results by rank, so only it moves with k. The test split's
definition questions are re-run at each depth and graded; results/evals/interior_depth.json.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mcp import Client
from readback_agent.run import Agent
from readback_evals.golden import load
from readback_evals.graders import grade
from readback_mcp_server.server import build_server
from readback_planner.floor import Floor


async def main() -> dict[str, object]:
    questions = [q for q in load(ROOT / "evals/golden") if q.family == "definition" and q.split == "test"]
    out: dict[str, object] = {"family": "definition", "split": "test", "questions": len(questions)}
    async with Client(build_server()) as client:
        for k in (3, 5, 8):
            Floor.definition_k = k
            agent = Agent()
            passed = 0
            for q in questions:
                turn = await agent.ask(client, q.question, provider="floor")
                passed += grade(q, turn.answer).passed  # type: ignore[arg-type]
            out[str(k)] = passed / len(questions)
    Floor.definition_k = 5
    path = ROOT / "results/evals/interior_depth.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    return out


if __name__ == "__main__":
    print(json.dumps(asyncio.run(main())))
