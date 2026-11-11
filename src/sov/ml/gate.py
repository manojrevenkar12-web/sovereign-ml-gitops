"""Release gate for an authority's adapter. Every check has a limit from config and a reason a person
can read in the merge request."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass

import numpy as np

from sov.config import platform


@dataclass
class Check:
    name: str
    passed: bool
    value: float
    limit: float
    reason: str


@dataclass
class Decision:
    promote: bool
    checks: list[Check]

    def summary(self) -> str:
        failed = [c.reason for c in self.checks if not c.passed]
        return "promote" if self.promote else "hold: " + "; ".join(failed)

    def to_dict(self) -> dict:
        return {"promote": self.promote, "summary": self.summary(), "checks": [asdict(c) for c in self.checks]}


def paired_lower_bound(cand: np.ndarray, champ: np.ndarray, reps: int, level: float, seed: int = 0) -> float:
    """One-sided lower bound (in accuracy points) of candidate minus champion on the same examples."""
    rng = np.random.default_rng(seed)
    diff = cand.astype(float) - champ.astype(float)
    n = len(diff)
    means = diff[rng.integers(0, n, size=(reps, n))].mean(axis=1)
    return float(np.percentile(means, (1 - level) * 100)) * 100


def recall(pred: Sequence[str], labels: Sequence[str], cls: str) -> float:
    idx = [i for i, y in enumerate(labels) if y == cls]
    if not idx:
        return float("nan")
    return sum(pred[i] == cls for i in idx) / len(idx)


def decide(
    cand_pred: Sequence[str],
    champ_pred: Sequence[str],
    labels: Sequence[str],
    critical: Sequence[str],
    residual_pii_per_1k: float,
    p95_ms: float,
    adapter_kb: float,
) -> Decision:
    g = platform()["gate"]
    y = np.array(labels)
    c_ok = np.array(cand_pred) == y
    h_ok = np.array(champ_pred) == y
    lb = paired_lower_bound(c_ok, h_ok, g["bootstrap_reps"], g["bootstrap_level"])
    checks = [
        Check(
            "training data pseudonymised",
            residual_pii_per_1k <= g["max_residual_pii_per_1k"],
            residual_pii_per_1k,
            g["max_residual_pii_per_1k"],
            f"training set still holds {residual_pii_per_1k:.1f} personal-data finds per 1,000 inquiries",
        ),
        Check(
            "not worse than champion",
            lb >= -g["non_inferiority_pts"],
            lb,
            -g["non_inferiority_pts"],
            f"accuracy vs champion could be {lb:+.1f} pts (limit -{g['non_inferiority_pts']:.1f})",
        ),
    ]
    for cls in critical:
        r = recall(list(cand_pred), list(labels), cls)
        checks.append(
            Check(
                f"recall {cls}",
                bool(r >= g["critical_recall_floor"]),
                r,
                g["critical_recall_floor"],
                f"{cls} recall {r:.0%} is below the {g['critical_recall_floor']:.0%} floor",
            )
        )
    checks += [
        Check(
            "latency",
            p95_ms <= g["max_p95_latency_ms"],
            p95_ms,
            g["max_p95_latency_ms"],
            f"p95 latency {p95_ms:.1f} ms over {g['max_p95_latency_ms']} ms",
        ),
        Check(
            "adapter size",
            adapter_kb <= g["max_adapter_kb"],
            adapter_kb,
            g["max_adapter_kb"],
            f"adapter is {adapter_kb:.0f} kB, over {g['max_adapter_kb']} kB",
        ),
    ]
    return Decision(all(c.passed for c in checks), checks)


def naive_decide(cand_pred: Sequence[str], champ_pred: Sequence[str], labels: Sequence[str]) -> bool:
    """Ship if validation accuracy is within the tolerance of the champion's: no interval, no privacy check."""
    tol = platform()["gate"]["naive"]["tolerance_pts"] / 100
    y = np.array(labels)
    return float((np.array(cand_pred) == y).mean()) >= float((np.array(champ_pred) == y).mean()) - tol
