"""Fetch every file data/warehouses.lock.json names, from each repository at its tag, and verify it.

Each file is downloaded from GitHub at the pinned tag, its SHA-256 compared with the lock, and
written to data/warehouses/<name>/<path>. A file whose digest differs, or that is missing at the tag,
stops the fetch with the path named: nothing is substituted and nothing is recomputed. A file already
on disk with the right digest is kept, so a second run downloads nothing.

    python scripts/fetch_warehouses.py            # fetch and verify
    python scripts/fetch_warehouses.py --verify   # verify what is on disk, download nothing
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RAW = "https://raw.githubusercontent.com/{owner}/{repo}/{tag}/{path}"


class FetchError(RuntimeError):
    pass


@dataclass(frozen=True)
class Item:
    warehouse: str
    repository: str
    tag: str
    path: str
    sha256: str


def load_lock(path: Path) -> dict[str, Any]:
    lock: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    if lock.get("version") != 1 or "warehouses" not in lock:
        raise FetchError(f"{path} is not a version 1 warehouse lock")
    return lock


def items(lock: dict[str, Any]) -> list[Item]:
    out: list[Item] = []
    for name, w in sorted(lock["warehouses"].items()):
        for entry in [*w["tables"], *w["documents"]]:
            out.append(Item(name, w["repository"], w["tag"], entry["path"], entry["sha256"]))
    return out


def target(base: Path, item: Item) -> Path:
    return base / item.warehouse / item.path


def digest_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def url_of(item: Item) -> str:
    owner, repo = item.repository.rstrip("/").split("/")[-2:]
    return RAW.format(owner=owner, repo=repo, tag=item.tag, path=item.path)


def download(item: Item, base: Path, get: Any) -> str:
    out = target(base, item)
    if out.exists() and digest_of(out) == item.sha256:
        return "kept"
    data = get(url_of(item))
    if data is None:
        raise FetchError(f"{item.warehouse}: {item.path} is not in {item.repository} at {item.tag}")
    found = hashlib.sha256(data).hexdigest()
    if found != item.sha256:
        raise FetchError(
            f"{item.warehouse}: {item.path} has digest {found[:12]}, "
            f"the lock says {item.sha256[:12]}; refusing it"
        )
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".part")
    tmp.write_bytes(data)
    tmp.replace(out)
    return "fetched"


def http_get(url: str) -> bytes | None:
    import httpx

    response = httpx.get(url, timeout=120.0, follow_redirects=True)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.content


def fetch(lock_path: Path, base: Path, get: Any = http_get, workers: int = 8) -> dict[str, int]:
    todo = items(load_lock(lock_path))
    counts = {"fetched": 0, "kept": 0}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for outcome in pool.map(lambda it: download(it, base, get), todo):
            counts[outcome] += 1
    return counts


def verify(lock_path: Path, base: Path) -> int:
    bad: list[str] = []
    todo = items(load_lock(lock_path))
    for item in todo:
        out = target(base, item)
        if not out.exists():
            bad.append(f"{item.warehouse}: {item.path} is missing")
        elif digest_of(out) != item.sha256:
            bad.append(f"{item.warehouse}: {item.path} does not match the lock")
    if bad:
        raise FetchError("the warehouses on disk do not match the lock:\n" + "\n".join(bad[:30]))
    return len(todo)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    lock_path = ROOT / "data" / "warehouses.lock.json"
    base = Path(os.environ.get("READBACK_WAREHOUSES", ROOT / "data" / "warehouses"))
    if args.verify:
        n = verify(lock_path, base)
        print(f"warehouses: {n} files match the lock")
        return 0
    counts = fetch(lock_path, base)
    n = verify(lock_path, base)
    if not args.quiet:
        print(f"warehouses: {counts['fetched']} fetched, {counts['kept']} already on disk, {n} verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
