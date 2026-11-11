"""Shared set-up for the ML evaluations: a base model per seed, cached in a scratch registry."""

from __future__ import annotations

import json
import os
from pathlib import Path

from sov.config import platform
from sov.ml import train
from sov.ml.pipeline import pseudonymise
from sov.ml.registry import Registry
from sov.world.inquiries import generic_corpus

SCRATCH = Path(os.environ.get("SOV_SCRATCH", "/tmp/sov-registry"))


def registry() -> Registry:
    return Registry(SCRATCH)


def base_for(seed: int) -> str:
    """Train (or reuse) the shared base on the generic corpus, pseudonymised like everything else."""
    index = SCRATCH / f"base-{seed}.digest"
    reg = registry()
    if index.exists():
        digest = index.read_text().strip()
        try:
            reg.get(digest)
            return digest
        except Exception:
            pass
    corpus = generic_corpus(platform()["eval"]["base_corpus"], seed)
    arrays = train.train_base(pseudonymise([q.text for q in corpus]), [q.handler_label for q in corpus])
    digest = reg.put(arrays, {"kind": "base", "seed": seed, "examples": len(corpus)})
    index.write_text(digest)
    return digest


def dump(obj) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False)
