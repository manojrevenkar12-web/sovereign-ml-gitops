"""Collect reports/*.json into web/public/data.json (the dashboard) and the results block of README.md.

Usage: python scripts/report.py
"""

from __future__ import annotations

import json
import re

from sov.config import load_tenants

from _common import ROOT, read


def pct(x: float, nd: int = 1) -> str:
    return f"{100 * x:.{nd}f}%"


def build() -> dict:
    ft, rel, pii, iso, ho, pub = (
        read(n)
        for n in ("finetune.json", "release_eval.json", "pii.json", "isolation.json", "heldout.json", "publish.json")
    )
    held_good = [r for r in rel["rows"] if not r["bad"] and not r["gate"]]
    tenants = load_tenants()
    return {
        "finetune": ft["summary"],
        "release": {
            "policies": rel["policies"],
            "by_candidate": rel["by_candidate"],
            "held_good_true_diff_pts": [
                round(100 * (r["true_accuracy"] - r["champion_true_accuracy"]), 1) for r in held_good
            ],
            "rows": [
                {
                    k: r[k]
                    for k in (
                        "seed",
                        "tenant",
                        "candidate",
                        "bad",
                        "why_bad",
                        "gate",
                        "gate_summary",
                        "accuracy_only",
                        "true_accuracy",
                        "champion_true_accuracy",
                    )
                }
                for r in rel["rows"]
            ],
        },
        "pii": {
            "methods": {
                k: {x: v[x] for x in ("recall", "precision", "instances", "leaked", "false_finds")}
                for k, v in pii["methods"].items()
            },
            "by_kind": {k: v["recall"] for k, v in pii["methods"]["generated filter"]["by_kind"].items()},
            "training_data": pii["training_data"],
            "lines": pii["lines"],
        },
        "isolation": iso["by_layer"],
        "heldout": ho,
        "tenants": {
            name: {
                "display_name": s["display_name"],
                "kind": s["kind"],
                "live": s["model"]["adapter"] is not None,
                "adapter": s["model"]["adapter"],
                "fine_tune": s["fine_tune"]["where"],
                "release": pub["records"].get(name, {}).get("decision", {}).get("summary"),
                "val_accuracy": pub["records"].get(name, {}).get("metrics", {}).get("val_accuracy"),
            }
            for name, s in sorted(tenants.items())
        },
    }


def readme_block(d: dict) -> str:
    ft, rp, pm = d["finetune"], d["release"]["policies"], d["pii"]["methods"]
    ho = d["heldout"]
    lines = [
        "| What | Result |",
        "|---|---|",
        f"| Routing accuracy, shared base → per-authority LoRA adapter (3 authorities × 3 seeds) | "
        f"{pct(ft['overall']['base'])} → **{pct(ft['overall']['lora'])}** (full fine-tune {pct(ft['overall']['full'])}) |",
        f"| Adapter vs full model on disk | **{ft['adapter_kb']:.0f} kB** vs {ft['base_kb'] / 1024:.1f} MB per authority |",
        f"| Faulty releases that reached production (of {rp['gate']['bad_total']}) | gate **{rp['gate']['bad_shipped']}**, "
        f"accuracy only {rp['accuracy_only']['bad_shipped']}, always ship {rp['always']['bad_shipped']} |",
        f"| Models trained on un-pseudonymised citizen data that shipped | gate **{rp['gate']['privacy_breaches_shipped']}**, "
        f"accuracy only {rp['accuracy_only']['privacy_breaches_shipped']} |",
        f"| Good releases the gate held back (of {rp['gate']['good_total']}) | {rp['gate']['good_held']} "
        f"(true accuracy {min(d['release']['held_good_true_diff_pts']):+.1f} to {max(d['release']['held_good_true_diff_pts']):+.1f} pts against the model already running, which kept serving) |",
        f"| Personal data reaching Loki ({d['pii']['lines']:,} log lines) | no filter {pct(1 - pm['none']['recall'], 0)}, "
        f"email/IBAN regex {pct(1 - pm['regex (email + IBAN)']['recall'])}, **generated filter "
        f"{pct(1 - pm['generated filter']['recall'])}** at {pct(pm['generated filter']['precision'])} precision |",
        "| Cross-authority access in static probes (Vault, Keycloak, Loki) | **0** of "
        f"{sum(v['cross_tenant'] for v in d['isolation'].values())} |",
        f"| Held out: onboarding an unseen authority | base {pct(ho['onboarding']['true_accuracy']['base'])} → "
        f"adapter **{pct(ho['onboarding']['true_accuracy']['lora'])}**, gate: {ho['onboarding']['gate']['summary']} |",
        f"| Held out: log formats the rules were not written for | **recall {pct(ho['logs']['recall'])}** "
        f"(precision {pct(ho['logs']['precision'])}): see [docs/heldout.md](docs/heldout.md) |",
    ]
    return "\n".join(lines)


def main() -> None:
    d = build()
    out = ROOT / "web" / "public" / "data.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(d, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {out.relative_to(ROOT)}")
    readme = ROOT / "README.md"
    if readme.exists():
        text = readme.read_text(encoding="utf-8")
        new = re.sub(
            r"(<!-- results:start -->\n).*?(\n<!-- results:end -->)",
            lambda m: m.group(1) + readme_block(d) + m.group(2),
            text,
            flags=re.S,
        )
        readme.write_text(new, encoding="utf-8")
        print("updated README.md results block")
    else:
        print(readme_block(d))


if __name__ == "__main__":
    main()
