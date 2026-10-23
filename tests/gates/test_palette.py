"""The palette validator, run against the committed values in both modes and on both cards."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")


def run(config: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(NODE), str(ROOT / "scripts/validate_palette.js"), "--config", str(config)],
        capture_output=True,
        text=True,
    )


def test_committed_palette_passes_both_modes_and_cards() -> None:
    result = run(ROOT / "web/src/theme/palette.json")
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout[result.stdout.index("{") :])
    assert report["failures"] == 0
    assert set(report["modes"]) == {"light", "dark"}


def test_a_low_contrast_slot_fails(tmp_path: Path) -> None:
    config = json.loads((ROOT / "web/src/theme/palette.json").read_text())
    config["dark"]["categorical"][0] = "#20232A"
    bad = tmp_path / "palette.json"
    bad.write_text(json.dumps(config))
    assert run(bad).returncode != 0


def test_an_empty_config_is_refused(tmp_path: Path) -> None:
    empty = tmp_path / "palette.json"
    empty.write_text("{}")
    assert run(empty).returncode != 0
