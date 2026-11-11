"""Markdown for the release merge request: one row per authority with the gate's checks.

Usage: python scripts/release_summary.py release-*.json > gate.md
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> None:
    rows = [r for path in sys.argv[1:] for r in json.loads(Path(path).read_text(encoding="utf-8"))]
    print("| Authority | Decision | Validation accuracy (champion) | Checks that failed |")
    print("|---|---|---|---|")
    for r in rows:
        m = r["metrics"]
        failed = [c["reason"] for c in r["decision"]["checks"] if not c["passed"]] if "checks" in r["decision"] else []
        print(
            f"| {r['tenant']} | {'promote' if r['decision']['promote'] else 'hold'} "
            f"| {m['val_accuracy']:.1%} ({m['champion_val_accuracy']:.1%}) | {'; '.join(failed) or '-'} |"
        )
    print("\nCandidates are content-addressed; the digests above are what Argo CD will run once this merges.")


if __name__ == "__main__":
    main()
