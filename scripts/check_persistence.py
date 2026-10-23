"""The out of process check: the API in its own process (the container in CI), one development
question through the floor, and the answer read back through a fresh database connection in a
third process, with its trace id matched to a stored span.

    python scripts/check_persistence.py                 # start the API locally on a free port
    python scripts/check_persistence.py --base-url URL  # against a running server and its DATABASE_URL
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
QUESTION = "What was the payment share in Denver in 2024?"


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def ask(base: str) -> dict[str, object]:
    answer: dict[str, object] = {}
    with httpx.stream(
        "POST", f"{base}/v1/chat", json={"question": QUESTION, "provider": "floor"}, timeout=180
    ) as r:
        for line in r.iter_lines():
            if line.startswith("data:"):
                event = json.loads(line[5:])
                if event.get("event") == "answer":
                    answer = event
    if not answer:
        raise SystemExit("the stream ended without an answer")
    return answer


READER = """
import json, sys, sqlalchemy as sa
from readback_api import db
eng = db.engine()
with eng.connect() as conn:
    row = conn.execute(
        sa.text("select verdict, trace_id from answers where id = :i"), {"i": sys.argv[1]}
    ).first()
    spans = conn.execute(
        sa.text("select count(*) from spans where trace_id = :t"), {"t": row[1] if row else ""}
    ).scalar()
print(json.dumps({
    "found": row is not None,
    "verdict": row[0] if row else None,
    "trace_id": row[1] if row else None,
    "spans": spans,
}))
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url")
    args = parser.parse_args()
    env = dict(os.environ)
    server = None
    if args.base_url:
        base = args.base_url.rstrip("/")
    else:
        port = free_port()
        env.update({"PORT": str(port), "READBACK_SQLITE": str(Path(tempfile.mkdtemp()) / "check.sqlite")})
        env.pop("DATABASE_URL", None)
        server = subprocess.Popen(
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
            stderr=subprocess.PIPE,
        )
        base = f"http://127.0.0.1:{port}"
        for _ in range(240):
            try:
                if httpx.get(f"{base}/health", timeout=2).status_code == 200:
                    break
            except httpx.HTTPError:
                time.sleep(0.5)
    try:
        answer = ask(base)
        time.sleep(0.5)
        reader = subprocess.run(
            [sys.executable, "-c", READER, str(answer["answer_id"])],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        seen = json.loads(reader.stdout.strip().splitlines()[-1])
    finally:
        if server is not None:
            server.terminate()
            server.wait(timeout=20)
    ok = (
        seen["found"]
        and seen["trace_id"] == answer["trace_id"]
        and seen["spans"] > 0
        and seen["verdict"] == "verified"
    )
    result = {
        "base_url": "a local server in its own process" if server is not None else base,
        "trace_id_matches": seen["trace_id"] == answer["trace_id"],
        "spans_stored": seen["spans"],
        "verdict": seen["verdict"],
        "read_back_in": "a third process with a fresh connection",
        "passed": ok,
    }
    (ROOT / "results" / "persistence.json").write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=1))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
