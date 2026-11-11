"""The release step for every authority: fine-tune on its export, gate against what it runs now, and
pin the new digest in tenants/<name>.yaml (in GitLab this commit goes in as a merge request).

Artifacts are written to artifacts/ (content-addressed); the image build copies them, production pulls them
from object storage.

Usage:
  python scripts/publish.py                         train, gate and pin every authority
  python scripts/publish.py --only T --dry-run      train and gate one authority; print the record as JSON
  python scripts/publish.py --pin-from rec.json...  pin the promoted candidates from earlier dry runs
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

from sov.config import load_tenants, platform
from sov.ml.pipeline import Export, release
from sov.ml.registry import Registry
from sov.world.inquiries import generate, with_archive

from _common import ROOT, write
from _ml import base_for, registry

ARTIFACTS = ROOT / "artifacts"


def pin(tenant: str, key: str, digest: str) -> None:
    path = ROOT / "tenants" / f"{tenant}.yaml"
    text = path.read_text(encoding="utf-8")
    text, n = re.subn(rf"(?m)^(  {key}: )\S+", rf"\g<1>{digest}", text, count=1)
    if n != 1:
        raise SystemExit(f"could not pin {key} in {path}")
    path.write_text(text, encoding="utf-8")


def run_one(tenant: str, spec: dict, base: str, seed: int, out: Registry) -> dict:
    cfg = platform()["eval"]
    need, crit = platform()["gate"]["min_critical_examples"], spec["model"]["critical"]
    inq = with_archive(generate(tenant, cfg["inquiries_per_tenant_train"], seed + 500), tenant, crit, need, seed + 500)
    val = with_archive(generate(tenant, cfg["inquiries_per_tenant_val"], seed + 600), tenant, crit, need, seed + 600)
    champion = spec["model"]["adapter"] if spec["model"]["base"] == base else None
    rec = release(
        Export(tenant, [q.text for q in inq], [q.handler_label for q in inq]),
        Export(tenant, [q.text for q in val], [q.handler_label for q in val]),
        out,
        base,
        champion,
        crit,
    )
    pinned = {s["model"]["adapter"] for s in load_tenants().values()}
    if not rec.decision["promote"] and rec.candidate not in pinned:
        for ext in ("npz", "json"):
            (ARTIFACTS / f"{rec.candidate.split(':')[1]}.{ext}").unlink(missing_ok=True)
    (ROOT / "reports" / "releases").mkdir(parents=True, exist_ok=True)
    (ROOT / "reports" / "releases" / f"{tenant}.json").write_text(rec.to_json() + "\n", encoding="utf-8")
    print(tenant, rec.decision["summary"], rec.candidate[:19], file=sys.stderr)
    return {
        "tenant": tenant,
        "base": base,
        "candidate": rec.candidate,
        "decision": rec.decision,
        "metrics": rec.metrics,
        "data_digest": rec.data_digest,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=platform()["eval"]["seeds"][0])
    ap.add_argument("--only")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--pin-from", nargs="+")
    args = ap.parse_args()

    if args.pin_from:
        for path in args.pin_from:
            for rec in json.loads(Path(path).read_text(encoding="utf-8")):
                if rec["decision"]["promote"]:
                    pin(rec["tenant"], "base", rec["base"])
                    pin(rec["tenant"], "adapter", rec["candidate"])
                    print(f"pinned {rec['tenant']} -> {rec['candidate']}", file=sys.stderr)
        return

    out = Registry(ARTIFACTS)
    scratch = registry()
    base = base_for(args.seed)
    for ext in ("npz", "json"):
        shutil.copy(scratch.root / f"{base.split(':')[1]}.{ext}", ARTIFACTS / f"{base.split(':')[1]}.{ext}")
    tenants = {k: v for k, v in sorted(load_tenants().items()) if args.only in (None, k)}
    records = [run_one(t, spec, base, args.seed, out) for t, spec in tenants.items()]
    if args.dry_run:
        print(json.dumps(records, indent=2, ensure_ascii=False))
        return
    for rec in records:
        if rec["decision"]["promote"]:
            pin(rec["tenant"], "base", rec["base"])
            pin(rec["tenant"], "adapter", rec["candidate"])
    write("publish.json", {"base": base, "records": {r["tenant"]: r for r in records}})


if __name__ == "__main__":
    main()
