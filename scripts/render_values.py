"""Write the Helm values Argo CD would build for each authority (as deploy/argocd/applicationset.yaml does),
so CI can lint and render the chart exactly as it will run.

Usage: python scripts/render_values.py build/values
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

from sov.config import load_tenants

from _common import ROOT  # noqa: F401


def main() -> None:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    for name, spec in sorted(load_tenants().items()):
        values = {
            "tenant": name,
            "model": {"base": spec["model"]["base"] or "", "adapter": spec["model"]["adapter"] or ""},
            "replicas": spec["serving"]["replicas"],
            "resources": {"cpu": spec["serving"]["cpu"], "memory": spec["serving"]["memory"]},
        }
        (out / f"{name}.yaml").write_text(yaml.safe_dump(values, sort_keys=False), encoding="utf-8")
        print(out / f"{name}.yaml")


if __name__ == "__main__":
    main()
