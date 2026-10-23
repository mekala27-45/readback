"""The recorded session the desk falls back to: web/public/data/recorded_session.json.

Starts the API in a subprocess on SQLite with no key, so the floor answers, and asks it a fixed set
of development split questions over the same /v1/chat stream the desk uses: one per family and
warehouse, a multi warehouse question, a refusal, and the ambiguous Portland lookup with its resume.
Every event is kept as the stream sent it, and each turn's spans as /v1/traces returns them. The
desk replays these when the API is asleep or absent and labels them as recorded. Questions come
from deploy/demo_questions.json so the recording and the demo queue cannot drift.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "web" / "public" / "data" / "recorded_session.json"
PICK = [
    "D-lookup-04",
    "T-lookup-01",
    "L-lookup-04",
    "D-comparison-01",
    "T-trend-04",
    "L-topk-01",
    "D-definition-05",
    "M-multi-06",
    "R-refusal-02",
]
AMBIGUOUS = "What was the payment share in Portland in 2019?"


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def stream(base: str, path: str, body: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    with httpx.stream("POST", f"{base}{path}", json=body, timeout=180) as r:
        r.raise_for_status()
        kind = "message"
        for line in r.iter_lines():
            if line.startswith("event:"):
                kind = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                event = json.loads(line[5:])
                event.setdefault("event", kind)
                out.append(event)
    return out


def main() -> None:
    port = free_port()
    env = {**os.environ, "PORT": str(port), "READBACK_SQLITE": str(Path(tempfile.mkdtemp()) / "rec.sqlite")}
    for key in ("DATABASE_URL", "GEMINI_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY", "SAMBANOVA_API_KEY"):
        env.pop(key, None)
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "readback_api.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        for _ in range(240):
            try:
                if httpx.get(f"{base}/health", timeout=2).status_code == 200:
                    break
            except httpx.HTTPError:
                time.sleep(0.5)
        health = httpx.get(f"{base}/health", timeout=10).json()
        questions = {
            q["id"]: q["question"]
            for q in json.loads((ROOT / "deploy" / "demo_questions.json").read_text(encoding="utf-8"))
        }
        turns = []
        for qid in PICK:
            turns.append(
                {
                    "id": qid,
                    "question": questions[qid],
                    "events": stream(base, "/v1/chat", {"question": questions[qid]}),
                }
            )
        first = stream(base, "/v1/chat", {"question": AMBIGUOUS})
        ask = next(e for e in first if e["event"] == "interrupt")
        choice = ask["candidates"][0]
        second = stream(base, f"/v1/chat/{ask['thread_id']}/resume", {"choice": choice})
        turns.append(
            {
                "id": "ambiguous-portland",
                "question": AMBIGUOUS,
                "events": first,
                "choice": choice,
                "resume": second,
            }
        )
        ids = sorted(
            {e["trace_id"] for t in turns for e in t["events"] + t.get("resume", []) if e.get("trace_id")}
        )
        time.sleep(1)  # spans are written after each stream closes
        traces = {i: httpx.get(f"{base}/v1/traces/{i}", timeout=10).json()["spans"] for i in ids}
    finally:
        proc.terminate()
        proc.wait(timeout=20)
    session = {
        "recorded": True,
        "recorded_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "provider": "floor",
        "health": health,
        "turns": turns,
        "traces": traces,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(session, indent=1, default=str) + "\n", encoding="utf-8")
    print(f"recorded {len(turns)} turns to {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
