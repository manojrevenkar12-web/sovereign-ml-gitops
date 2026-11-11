"""Release candidates with known faults, decided three ways and scored against the truth.

Each authority has a champion adapter in production. Six candidates arrive:
  refresh        a fresh export, pseudonymised                      (expected good)
  unredacted     the same export, but the fine-tune job skipped pseudonymisation (privacy breach)
  wrong-tenant   another authority's export uploaded by mistake
  stale          an export from before the authority reorganised
  label-noise    30% of case-handler labels scrambled by an export bug
  missing-urgent the ticket system lost every hazard report ("baum auf der straße")
Policies: the gate, "accuracy only" (ship if within 1 pt of the champion) and "always ship".

Usage: python scripts/release_eval.py
"""

from __future__ import annotations

import random

from sov.config import load_tenants, platform
from sov.evals import accuracy
from sov.ml import train
from sov.ml.gate import naive_decide, recall
from sov.ml.pipeline import ContractError, Export, pseudonymise, release
from sov.world.inquiries import generate, with_archive, world

from _common import write
from _ml import base_for, registry

FAULTS = ["refresh", "unredacted", "wrong-tenant", "stale", "label-noise", "missing-urgent"]


def candidate_export(kind: str, tenant: str, n: int, seed: int, others: list[str], critical: list[str]) -> Export:
    """Every export is topped up from the archive the way the team does it; the faults happen upstream."""
    rng = random.Random(f"{kind}:{tenant}:{seed}")
    need = platform()["gate"]["min_critical_examples"]
    if kind == "wrong-tenant":
        src = rng.choice(others)
        inq = with_archive(generate(tenant, n, seed + 7, vocab_from=src), src, critical, need, seed + 7)
    elif kind == "stale":
        inq = with_archive(
            generate(tenant, n, seed + 7, after_reorg=False), tenant, critical, need, seed + 7, after_reorg=False
        )
    else:
        inq = with_archive(generate(tenant, n, seed + 7), tenant, critical, need, seed + 7)
    if kind == "missing-urgent":  # the hazard reports never reach the export, archive included
        inq = [q for q in inq if q.topic != "gefahr"]
    labels = [q.handler_label for q in inq]
    if kind == "label-noise":
        depts = world()["departments"]
        labels = [rng.choice(depts) if rng.random() < 0.30 else y for y in labels]
    return Export(tenant, [q.text for q in inq], labels, pseudonymise=(kind != "unredacted"))


def main() -> None:
    cfg = platform()["eval"]
    floor = platform()["gate"]["critical_recall_floor"]
    reg = registry()
    tenants = load_tenants()
    rows = []
    for seed in cfg["seeds"]:
        base = base_for(seed)
        base_arrays = reg.get(base)
        for tenant, spec in sorted(tenants.items()):
            critical = spec["model"]["critical"]
            others = [t for t in tenants if t != tenant]
            # champion: trained on last quarter's export (before any reorganisation)
            need = platform()["gate"]["min_critical_examples"]
            old = with_archive(
                generate(tenant, cfg["inquiries_per_tenant_train"], seed + 3, after_reorg=False),
                tenant,
                critical,
                need,
                seed + 3,
                after_reorg=False,
            )
            champion = reg.put(
                train.train_adapter(
                    base_arrays, pseudonymise([q.text for q in old]), [q.handler_label for q in old], critical
                ),
                {"kind": "adapter", "tenant": tenant, "base": base},
            )
            val_inq = with_archive(
                generate(tenant, cfg["inquiries_per_tenant_val"], seed + 11), tenant, critical, need, seed + 11
            )
            validation = Export(tenant, [q.text for q in val_inq], [q.handler_label for q in val_inq])
            test = generate(tenant, cfg["inquiries_per_tenant_test"], seed + 1000)
            test_x, test_y = pseudonymise([q.text for q in test]), [q.true_dept for q in test]
            champ_pred_test = train.Predictor(base_arrays, reg.get(champion)).predict(test_x)
            champ_true = accuracy(champ_pred_test, test_y)
            champ_val = train.Predictor(base_arrays, reg.get(champion)).predict(pseudonymise(validation.texts))
            for kind in FAULTS:
                export = candidate_export(kind, tenant, cfg["inquiries_per_tenant_train"], seed, others, critical)
                contract_error = None
                try:
                    rec = release(export, validation, reg, base, champion, critical)
                except ContractError as exc:  # the gate path stops here; train anyway to score the others
                    contract_error = str(exc)
                    rec = release(export, validation, reg, base, champion, critical, enforce_contract=False)
                    rec.decision = {"promote": False, "summary": f"hold: contract: {contract_error}"}
                cand = train.Predictor(base_arrays, reg.get(rec.candidate))
                pred_test = cand.predict(test_x)
                true_acc = accuracy(pred_test, test_y)
                true_crit = min(recall(pred_test, test_y, c) for c in critical)
                bad_reasons = []
                if not export.pseudonymise:
                    bad_reasons.append("personal data in the model")
                if true_acc < champ_true - 0.01:
                    bad_reasons.append(f"true accuracy {100 * (true_acc - champ_true):+.1f} pts")
                if true_crit < floor:
                    bad_reasons.append(f"true {critical[0]} recall {true_crit:.0%}")
                cand_val = cand.predict(pseudonymise(validation.texts))
                rows.append(
                    {
                        "seed": seed,
                        "tenant": tenant,
                        "candidate": kind,
                        "bad": bool(bad_reasons),
                        "why_bad": bad_reasons,
                        "true_accuracy": true_acc,
                        "champion_true_accuracy": champ_true,
                        "true_critical_recall": true_crit,
                        "gate": rec.decision["promote"],
                        "gate_summary": rec.decision["summary"],
                        "accuracy_only": naive_decide(cand_val, champ_val, validation.labels),
                        "always": True,
                        "val_accuracy": rec.metrics["val_accuracy"],
                        "champion_val_accuracy": rec.metrics["champion_val_accuracy"],
                    }
                )
                r = rows[-1]
                print(
                    seed,
                    tenant,
                    kind,
                    "bad" if r["bad"] else "good",
                    "gate",
                    r["gate"],
                    "acc-only",
                    r["accuracy_only"],
                    round(true_acc, 3),
                    round(champ_true, 3),
                    round(true_crit, 2),
                )

    def outcome(policy: str) -> dict:
        bad = [r for r in rows if r["bad"]]
        good = [r for r in rows if not r["bad"]]
        return {
            "bad_shipped": sum(r[policy] for r in bad),
            "bad_total": len(bad),
            "good_held": sum(not r[policy] for r in good),
            "good_total": len(good),
            "privacy_breaches_shipped": sum(r[policy] for r in bad if "personal data in the model" in r["why_bad"]),
        }

    by_kind = {
        k: {
            "bad": sum(r["bad"] for r in rows if r["candidate"] == k),
            "n": sum(r["candidate"] == k for r in rows),
            **{p: sum(r[p] for r in rows if r["candidate"] == k) for p in ("gate", "accuracy_only", "always")},
        }
        for k in FAULTS
    }
    write(
        "release_eval.json",
        {
            "rows": rows,
            "policies": {p: outcome(p) for p in ("gate", "accuracy_only", "always")},
            "by_candidate": by_kind,
        },
    )


if __name__ == "__main__":
    main()
