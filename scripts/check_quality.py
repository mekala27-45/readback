"""The quality gate: lint, format, types and tests with coverage, written to results/quality.json.

It runs ruff check, ruff format --check, mypy (strict, over the packages listed in pyproject.toml)
and the test suite with coverage, then writes one small record of what each said. The record is
evidence for the release checklist, so it is written from the tools' own output, never by hand.
It exits nonzero unless every check is clean and coverage is at least the floor.

    uv run python scripts/check_quality.py
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "quality.json"
TARGETS = ["packages", "scripts", "tests"]
COVERAGE_FLOOR = 80.0


def run(args: list[str]) -> subprocess.CompletedProcess[str]:
    """Run one tool from the repository root and keep its output."""
    return subprocess.run(args, cwd=ROOT, capture_output=True, text=True, check=False)


def mypy_errors(output: str) -> int:
    """The error count mypy printed; zero when it found none."""
    found = re.search(r"Found (\d+) errors?", output)
    if found:
        return int(found.group(1))
    return sum(1 for line in output.splitlines() if ": error:" in line)


def count_tests(junit: Path) -> tuple[int, int]:
    """Passed and failed tests from the JUnit report. Errors count as failed."""
    if not junit.exists():
        return 0, 0
    root = ET.parse(junit).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
    total = failed = skipped = 0
    for suite in suites:
        total += int(suite.get("tests", 0))
        failed += int(suite.get("failures", 0)) + int(suite.get("errors", 0))
        skipped += int(suite.get("skipped", 0))
    return total - failed - skipped, failed


def coverage_percent(report: Path) -> float:
    """The total line coverage from the coverage JSON report, to one decimal."""
    if not report.exists():
        return 0.0
    data = json.loads(report.read_text(encoding="utf-8"))
    return round(float(data["totals"]["percent_covered"]), 1)


def main() -> int:
    ruff = run(["ruff", "check", *TARGETS])
    ruff_format = run(["ruff", "format", "--check", *TARGETS])
    mypy = run(["mypy"])
    with tempfile.TemporaryDirectory() as tmp:
        cov_json = Path(tmp) / "coverage.json"
        junit = Path(tmp) / "junit.xml"
        tests = run(
            [
                sys.executable,
                "-m",
                "pytest",
                "--cov",
                "--cov-report=",
                f"--cov-report=json:{cov_json}",
                f"--junitxml={junit}",
                "-p",
                "no:cacheprovider",
            ]
        )
        coverage = coverage_percent(cov_json)
        passed_tests, failed_tests = count_tests(junit)
    errors = mypy_errors(mypy.stdout + mypy.stderr)
    record = {
        "ruff": ruff.returncode == 0,
        "ruff_format": ruff_format.returncode == 0,
        "mypy": mypy.returncode == 0 and errors == 0,
        "mypy_errors": errors,
        "coverage": coverage,
        "tests": passed_tests,
        "failed": failed_tests,
    }
    record["passed"] = bool(
        record["ruff"]
        and record["ruff_format"]
        and record["mypy"]
        and failed_tests == 0
        and tests.returncode == 0
        and coverage >= COVERAGE_FLOOR
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(
        f"quality: ruff {'clean' if record['ruff'] else 'not clean'}, "
        f"format {'clean' if record['ruff_format'] else 'not clean'}, "
        f"mypy {errors} errors, coverage {coverage}%, "
        f"{passed_tests} passed, {failed_tests} failed"
    )
    if not record["passed"]:
        for name, proc in (("ruff", ruff), ("ruff format", ruff_format), ("mypy", mypy)):
            if proc.returncode != 0:
                print(f"\n{name}:\n{proc.stdout}{proc.stderr}".rstrip())
        if tests.returncode != 0:
            print("\npytest:\n" + "\n".join(tests.stdout.splitlines()[-30:]))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
