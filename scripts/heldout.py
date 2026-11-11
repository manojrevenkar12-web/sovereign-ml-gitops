"""The held-out run, once. Pinned in config/heldout.lock before it ran (see docs/heldout.md):

1. Onboarding an authority nobody looked at while building the pipeline (stadt-ostmark): its own routing,
   words and departments.
2. Log formats the redaction rules were not written against.

Refuses to run when the pinned files changed, and refuses to run twice.
Usage: python scripts/heldout.py
"""

from __future__ import annotations

import hashlib
import json
import sys

from sov.config import load_tenants, platform
from sov.evals import accuracy, score_redaction
from sov.ml import train
from sov.ml.gate import recall
from sov.ml.pipeline import Export, pseudonymise, release
from sov.pii.redact import redact
from sov.world.inquiries import generate, with_archive
from sov.world.pii import heldout_log_corpus

from _common import REPORTS, ROOT, write
from _ml import base_for, registry

LOCK = ROOT / "config" / "heldout.lock"


def digest(paths: list[str]) -> dict[str, str]:
    return {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in paths}


def main() -> int:
    lock = json.loads(LOCK.read_text())
    now = digest(list(lock["files"]))
    changed = [p for p, h in lock["files"].items() if now[p] != h]
    if changed:
        print(f"refusing: pinned files changed since the lock: {changed}", file=sys.stderr)
        return 1
    if (REPORTS / "heldout.json").exists():
        print("refusing: the held-out run already happened (reports/heldout.json)", file=sys.stderr)
        return 1

    cfg = platform()["eval"]
    reg = registry()
    seed = lock["seed"]
    tenant = "stadt-ostmark"
    critical = ["ordnungsamt"]
    need = platform()["gate"]["min_critical_examples"]
    base = base_for(cfg["seeds"][0])
    base_arrays = reg.get(base)
    tr = with_archive(generate(tenant, cfg["inquiries_per_tenant_train"], seed), tenant, critical, need, seed)
    val = with_archive(generate(tenant, cfg["inquiries_per_tenant_val"], seed + 1), tenant, critical, need, seed + 1)
    test = generate(tenant, cfg["inquiries_per_tenant_test"], seed + 2)
    rec = release(
        Export(tenant, [q.text for q in tr], [q.handler_label for q in tr]),
        Export(tenant, [q.text for q in val], [q.handler_label for q in val]),
        reg,
        base,
        None,
        critical,
    )
    test_x, test_y = pseudonymise([q.text for q in test]), [q.true_dept for q in test]
    pred_lora = train.Predictor(base_arrays, reg.get(rec.candidate)).predict(test_x)
    onboarding = {
        "tenant": tenant,
        "gate": rec.decision,
        "true_accuracy": {
            "base": accuracy(train.Predictor(base_arrays).predict(test_x), test_y),
            "lora": accuracy(pred_lora, test_y),
        },
        "true_critical_recall": recall(pred_lora, test_y, "ordnungsamt"),
    }

    lines = heldout_log_corpus(cfg["log_lines"], seed, sorted(load_tenants()))
    found = [[(f.kind, f.start, f.end) for f in redact(ln.text)[1]] for ln in lines]
    logs = score_redaction(lines, found)
    by_source = {}
    for src in sorted({ln.source for ln in lines}):
        idx = [i for i, ln in enumerate(lines) if ln.source == src]
        s = score_redaction([lines[i] for i in idx], [found[i] for i in idx])
        by_source[src] = {"instances": s["instances"], "recall": s["recall"], "false_finds": s["false_finds"]}
    write(
        "heldout.json",
        {
            "lock": lock,
            "onboarding": onboarding,
            "logs": {k: logs[k] for k in ("recall", "precision", "instances", "caught", "false_finds")}
            | {"by_kind": logs["by_kind"], "by_source": by_source},
        },
    )
    print(json.dumps(onboarding, indent=1))
    print({k: logs[k] for k in ("recall", "precision")}, json.dumps(by_source))
    return 0


if __name__ == "__main__":
    sys.exit(main())
