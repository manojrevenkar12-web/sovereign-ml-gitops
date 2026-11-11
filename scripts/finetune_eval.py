"""Per-authority fine-tuning: shared base only, LoRA adapter, full fine-tune. Accuracy on the truth,
plus what each costs to store and serve.

Usage: python scripts/finetune_eval.py
"""

from __future__ import annotations

import time

import numpy as np

from sov.config import load_tenants, platform
from sov.evals import accuracy
from sov.ml import train
from sov.ml.pipeline import pseudonymise
from sov.ml.registry import pack
from sov.world.inquiries import generate

from _common import write
from _ml import base_for, registry


def main() -> None:
    cfg = platform()["eval"]
    reg = registry()
    rows = []
    for seed in cfg["seeds"]:
        base_digest = base_for(seed)
        base = reg.get(base_digest)
        for tenant in sorted(load_tenants()):
            tr = generate(tenant, cfg["inquiries_per_tenant_train"], seed)
            te = generate(tenant, cfg["inquiries_per_tenant_test"], seed + 1000)
            tr_x, tr_y = pseudonymise([q.text for q in tr]), [q.handler_label for q in tr]
            te_x, te_y = pseudonymise([q.text for q in te]), [q.true_dept for q in te]
            t = time.perf_counter()
            adapter = train.train_adapter(base, tr_x, tr_y, load_tenants()[tenant]["model"]["critical"])
            t_adapter = time.perf_counter() - t
            t = time.perf_counter()
            full = train.train_full(base, tr_x, tr_y)
            t_full = time.perf_counter() - t
            p_base, p_lora, p_full = train.Predictor(base), train.Predictor(base, adapter), train.Predictor(full)
            rows.append(
                {
                    "seed": seed,
                    "tenant": tenant,
                    "base": accuracy(p_base.predict(te_x), te_y),
                    "lora": accuracy(p_lora.predict(te_x), te_y),
                    "full": accuracy(p_full.predict(te_x), te_y),
                    "train_seconds": {"lora": t_adapter, "full": t_full},
                    "p95_ms": {"lora": p_lora.latency_ms(te_x)["p95"], "full": p_full.latency_ms(te_x)["p95"]},
                }
            )
            print(
                rows[-1]["tenant"],
                seed,
                round(rows[-1]["base"], 3),
                round(rows[-1]["lora"], 3),
                round(rows[-1]["full"], 3),
            )
    base_kb = len(pack(reg.get(base_for(cfg["seeds"][0])))) / 1024
    adapter_kb = len(pack(train.train_adapter.__globals__["to_arrays"](train.new_adapter()))) / 1024

    def mean(key: str, tenant: str | None = None) -> float:
        return float(np.mean([r[key] for r in rows if tenant in (None, r["tenant"])]))

    write(
        "finetune.json",
        {
            "rows": rows,
            "summary": {
                "by_tenant": {t: {k: mean(k, t) for k in ("base", "lora", "full")} for t in sorted(load_tenants())},
                "overall": {k: mean(k) for k in ("base", "lora", "full")},
                "base_kb": base_kb,
                "adapter_kb": adapter_kb,
                "adapter_params": train.new_adapter().n_params(),
                "base_params": train.new_router().n_params(),
                "train_seconds": {k: float(np.mean([r["train_seconds"][k] for r in rows])) for k in ("lora", "full")},
                "p95_ms": {k: float(np.mean([r["p95_ms"][k] for r in rows])) for k in ("lora", "full")},
            },
        },
    )


if __name__ == "__main__":
    main()
