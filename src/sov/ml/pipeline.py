"""The ML pipeline as it runs in GitLab CI (and as Kubernetes Jobs for fine-tuning):

    contract -> pseudonymise -> fine-tune adapter -> evaluate against champion -> gate -> record

Every step writes what it did into the release record, so an auditor can trace a served answer back to
the adapter digest, the training-data digest, the base digest and the commit that built them.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from typing import Any

from sov.config import platform
from sov.ml import train
from sov.ml.gate import Decision, decide
from sov.ml.registry import Registry
from sov.pii.redact import redact


class ContractError(ValueError):
    pass


@dataclass
class Export:
    """What an authority's ticket system hands over: text and the department a case handler chose."""

    tenant: str
    texts: list[str]
    labels: list[str]
    pseudonymise: bool = True  # False models a job started by hand on the raw export


@dataclass
class ReleaseRecord:
    tenant: str
    candidate: str
    champion: str | None
    base: str
    data_digest: str
    commit: str
    decision: dict[str, Any]
    metrics: dict[str, Any] = field(default_factory=dict)
    steps: list[dict[str, Any]] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True, ensure_ascii=False)


def commit() -> str:
    return os.environ.get("CI_COMMIT_SHA") or os.environ.get("GITHUB_SHA") or "local"


def contract(export: Export, critical: Sequence[str] = ()) -> None:
    if len(export.texts) != len(export.labels):
        raise ContractError("texts and labels differ in length")
    unknown = sorted(set(export.labels) - set(train.DEPARTMENTS))
    if unknown:
        raise ContractError(f"labels outside the department list: {unknown}")
    if len(export.texts) < 100:
        raise ContractError(f"{len(export.texts)} examples; at least 100 are needed")
    need = platform()["gate"]["min_critical_examples"]
    short = {c: export.labels.count(c) for c in critical if export.labels.count(c) < need}
    if short:
        raise ContractError(
            "too few examples of critical departments " + ", ".join(f"{c}: {n} of {need}" for c, n in short.items())
        )


def pseudonymise(texts: Sequence[str]) -> list[str]:
    return [redact(t)[0] for t in texts]


def residual_per_1k(texts: Sequence[str]) -> float:
    """Personal data the redactor still finds in a training set (0 after the pseudonymise step)."""
    finds = sum(len(redact(t)[1]) for t in texts)
    return 1000 * finds / max(1, len(texts))


def data_digest(texts: Sequence[str], labels: Sequence[str]) -> str:
    h = hashlib.sha256()
    for t, y in zip(texts, labels, strict=True):
        h.update(json.dumps([t, y], ensure_ascii=False).encode("utf-8") + b"\n")
    return "sha256:" + h.hexdigest()


def release(
    export: Export,
    validation: Export,
    registry: Registry,
    base: str,
    champion: str | None,
    critical: Sequence[str],
    enforce_contract: bool = True,
) -> ReleaseRecord:
    """Raises ContractError before any training when the export breaks the contract."""
    steps: list[dict[str, Any]] = []

    t0 = time.perf_counter()
    contract(validation, critical)
    if enforce_contract:
        contract(export, critical)
    steps.append({"step": "contract", "ok": enforce_contract, "examples": len(export.texts)})

    texts = pseudonymise(export.texts) if export.pseudonymise else list(export.texts)
    val_texts = pseudonymise(validation.texts)
    steps.append({"step": "pseudonymise", "ran": export.pseudonymise})

    base_arrays = registry.get(base)
    adapter = train.train_adapter(base_arrays, texts, export.labels, critical)
    digest = data_digest(texts, export.labels)
    candidate = registry.put(
        adapter,
        {
            "kind": "adapter",
            "tenant": export.tenant,
            "base": base,
            "data": digest,
            "commit": commit(),
            "examples": len(texts),
        },
    )
    steps.append({"step": "fine-tune", "seconds": round(time.perf_counter() - t0, 1)})

    cand = train.Predictor(base_arrays, registry.get(candidate))
    champ = train.Predictor(base_arrays, registry.get(champion) if champion else None)
    cand_pred = cand.predict(val_texts)
    champ_pred = champ.predict(val_texts)
    latency = cand.latency_ms(val_texts, n=200)
    decision: Decision = decide(
        cand_pred,
        champ_pred,
        validation.labels,
        critical,
        residual_per_1k(texts),
        latency["p95"],
        registry.size_kb(candidate),
    )
    steps.append({"step": "gate", "promote": decision.promote})

    acc = lambda p: sum(a == b for a, b in zip(p, validation.labels, strict=True)) / len(p)  # noqa: E731
    return ReleaseRecord(
        tenant=export.tenant,
        candidate=candidate,
        champion=champion,
        base=base,
        data_digest=digest,
        commit=commit(),
        decision=decision.to_dict(),
        metrics={
            "val_accuracy": acc(cand_pred),
            "champion_val_accuracy": acc(champ_pred),
            "p95_ms": latency["p95"],
            "adapter_kb": registry.size_kb(candidate),
        },
        steps=steps,
    )
