"""Shared helpers for the evaluation scripts."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

REPORTS = ROOT / "reports"


def write(name: str, data: Any) -> Path:
    REPORTS.mkdir(exist_ok=True)
    path = REPORTS / name
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=False) + "\n", encoding="utf-8")
    print(f"wrote {path.relative_to(ROOT)}")
    return path


def read(name: str) -> Any:
    return json.loads((REPORTS / name).read_text(encoding="utf-8"))
