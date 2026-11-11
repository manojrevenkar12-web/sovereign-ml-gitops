"""Run the isolation probes. With --rendered DIR (helm template output, one file per authority) the
network layer is checked as well; CI does that after rendering the chart.

Usage: python scripts/isolation_check.py [--rendered build/rendered]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sov.config import load_tenants
from sov.tenancy.isolation import load_rendered, loki_probes, network_probes, summary, token_probes, vault_probes

from _common import write


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rendered", type=Path)
    ap.add_argument("--out", default="isolation.json")
    args = ap.parse_args()
    specs = load_tenants()
    names = sorted(specs)
    probes = vault_probes(names) + token_probes(specs) + loki_probes(names)
    if args.rendered:
        probes += network_probes(load_rendered(args.rendered))
    result = summary(probes)
    write(args.out, result)
    for layer, s in result["by_layer"].items():
        print(
            f"{layer:9s} cross-authority allowed {s['cross_tenant_allowed']}/{s['cross_tenant']}  "
            f"own allowed {s['own_allowed']}/{s['own']}"
        )
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
