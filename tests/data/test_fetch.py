"""The fetch: digests checked, a planted wrong digest refused, a missing file refused."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from scripts import fetch_warehouses as f


def lock(tmp_path: Path, payload: bytes, digest: str | None = None) -> Path:
    data = {
        "version": 1,
        "warehouses": {
            "demo": {
                "repository": "https://github.com/example/demo",
                "tag": "v0.1.0",
                "commit": "0" * 40,
                "tables": [{"path": "results/a.parquet", "table": "a", "sha256": digest or hashlib.sha256(payload).hexdigest(), "bytes": len(payload)}],
                "documents": [],
            }
        },
    }
    path = tmp_path / "lock.json"
    path.write_text(json.dumps(data))
    return path


def test_fetch_writes_a_verified_file(tmp_path: Path) -> None:
    payload = b"parquet bytes"
    counts = f.fetch(lock(tmp_path, payload), tmp_path / "w", get=lambda url: payload)
    assert counts == {"fetched": 1, "kept": 0}
    assert (tmp_path / "w/demo/results/a.parquet").read_bytes() == payload
    assert f.fetch(lock(tmp_path, payload), tmp_path / "w", get=lambda url: b"never")["kept"] == 1


def test_a_planted_wrong_digest_is_refused(tmp_path: Path) -> None:
    with pytest.raises(f.FetchError, match="refusing it"):
        f.fetch(lock(tmp_path, b"x", digest="f" * 64), tmp_path / "w", get=lambda url: b"x")
    assert not (tmp_path / "w/demo/results/a.parquet").exists()


def test_a_file_missing_at_the_tag_is_refused(tmp_path: Path) -> None:
    with pytest.raises(f.FetchError, match="is not in"):
        f.fetch(lock(tmp_path, b"x"), tmp_path / "w", get=lambda url: None)


def test_the_url_names_the_tag(tmp_path: Path) -> None:
    item = f.Item("demo", "https://github.com/example/demo", "v0.1.0", "results/a.parquet", "0")
    assert f.url_of(item) == "https://raw.githubusercontent.com/example/demo/v0.1.0/results/a.parquet"


def test_the_committed_lock_names_three_warehouses_at_tags() -> None:
    data = f.load_lock(Path(__file__).resolve().parents[2] / "data/warehouses.lock.json")
    assert sorted(data["warehouses"]) == ["doorstep", "ledger", "turnaround"]
    for w in data["warehouses"].values():
        assert w["tag"] == "v0.1.0" and len(w["commit"]) == 40 and w["tables"]
