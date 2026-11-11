"""How much personal data reaches Loki: no filter, a typical email/IBAN regex, and the generated filter.

Usage: python scripts/pii_eval.py
"""

from __future__ import annotations

import re

from sov.config import load_tenants, platform
from sov.evals import score_redaction
from sov.pii.redact import redact
from sov.world.inquiries import generate
from sov.world.pii import log_corpus

from _common import write

NAIVE = [("email", re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")), ("iban", re.compile(r"DE\d{2}(?: ?\d{4}){4} ?\d{2}"))]


def naive(text: str) -> list[tuple[str, int, int]]:
    return [(k, m.start(), m.end()) for k, rx in NAIVE for m in rx.finditer(text)]


def ours(text: str) -> list[tuple[str, int, int]]:
    return [(f.kind, f.start, f.end) for f in redact(text)[1]]


def main() -> None:
    cfg = platform()["eval"]
    tenants = sorted(load_tenants())
    rows = {"none": [], "regex (email + IBAN)": [], "generated filter": []}
    by_source: dict[str, list] = {}
    for seed in cfg["seeds"]:
        lines = log_corpus(cfg["log_lines"], seed, tenants)
        found_ours = [ours(ln.text) for ln in lines]
        rows["none"].append(score_redaction(lines, [[] for _ in lines]))
        rows["regex (email + IBAN)"].append(score_redaction(lines, [naive(ln.text) for ln in lines]))
        rows["generated filter"].append(score_redaction(lines, found_ours))
        for src in sorted({ln.source for ln in lines}):
            idx = [i for i, ln in enumerate(lines) if ln.source == src]
            by_source.setdefault(src, []).append(score_redaction([lines[i] for i in idx], [found_ours[i] for i in idx]))

    def pooled(scores: list[dict]) -> dict:
        inst = sum(s["instances"] for s in scores)
        caught = sum(s["caught"] for s in scores)
        found = sum(s["found"] for s in scores)
        false = sum(s["false_finds"] for s in scores)
        kinds = {}
        for k in scores[0]["by_kind"]:
            i = sum(s["by_kind"][k]["instances"] for s in scores)
            c = sum(s["by_kind"][k]["caught"] for s in scores)
            kinds[k] = {"instances": i, "caught": c, "recall": c / i if i else None}
        return {
            "instances": inst,
            "caught": caught,
            "leaked": inst - caught,
            "recall": caught / max(1, inst),
            "found": found,
            "false_finds": false,
            "precision": (found - false) / max(1, found),
            "by_kind": kinds,
        }

    # Personal data left in training data after the pipeline's pseudonymise step
    training = {}
    for tenant in tenants:
        inq = generate(tenant, cfg["inquiries_per_tenant_train"], cfg["seeds"][0])
        from sov.world.pii import LogLine

        lines = [LogLine("inquiry", q.text, q.pii) for q in inq]
        s = score_redaction(lines, [ours(q.text) for q in inq])
        training[tenant] = {
            "inquiries": len(inq),
            "with_pii": sum(bool(q.pii) for q in inq),
            "instances": s["instances"],
            "left": s["instances"] - s["caught"],
            "left_per_1k_inquiries": 1000 * (s["instances"] - s["caught"]) / len(inq),
            "recall": s["recall"],
        }

    write(
        "pii.json",
        {
            "lines": cfg["log_lines"] * len(cfg["seeds"]),
            "methods": {k: pooled(v) for k, v in rows.items()},
            "by_source": {k: pooled(v) for k, v in by_source.items()},
            "training_data": training,
        },
    )


if __name__ == "__main__":
    main()
