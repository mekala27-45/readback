"""Build catalog/ from the fetched warehouses. See packages/catalog/src/readback_catalog/build.py."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

from readback_catalog.build import build

if __name__ == "__main__":
    summary = build(ROOT)
    print(json.dumps(summary, indent=1))
    sys.exit(0)
