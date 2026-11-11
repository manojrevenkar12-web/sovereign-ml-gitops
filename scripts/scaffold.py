"""Render deploy/generated/ from tenants/*.yaml. --check: fail if the committed files are stale."""

from __future__ import annotations

import sys

from sov.config import load_tenants
from sov.tenancy.scaffold import render

from _common import ROOT


def main() -> int:
    files = render(load_tenants())
    stale = [p for p, text in files.items() if not p.exists() or p.read_text(encoding="utf-8") != text]
    if "--check" in sys.argv:
        for p in stale:
            print(f"stale: {p.relative_to(ROOT)} (run python scripts/scaffold.py)", file=sys.stderr)
        return 1 if stale else 0
    for p, text in files.items():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    print(f"wrote {len(files)} files under deploy/generated/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
