"""Inference in numpy. The serving image carries no torch; tests/test_ml.py checks that this forward pass
gives the same probabilities as the torch model it was trained as."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from sov.config import platform
from sov.ml.features import FeatureSpec, features

DEPARTMENTS = [
    "meldewesen",
    "kfz",
    "fuehrerschein",
    "standesamt",
    "gewerbe",
    "sozialleistungen",
    "bauamt",
    "ordnungsamt",
    "steuern",
    "abfall",
    "kita",
    "elterngeld",
    "extern",
]


def _spec() -> FeatureSpec:
    m = platform()["model"]
    return FeatureSpec(m["buckets"], m["char_ngrams"][0], m["char_ngrams"][1], m["word_bigrams"])


class NumpyRouter:
    def __init__(self, base: dict[str, np.ndarray], adapter: dict[str, np.ndarray] | None = None):
        f = lambda a: np.asarray(a, dtype=np.float32)  # noqa: E731
        self.emb, self.fc_w, self.fc_b = f(base["emb.weight"]), f(base["fc.weight"]), f(base["fc.bias"])
        self.head_w, self.head_b = f(base["head.weight"]), f(base["head.bias"])
        self.adapter = None
        if adapter is not None:
            a = platform()["train"]["adapter"]
            self.adapter = {k: f(v) for k, v in adapter.items()}
            self.scale = a["alpha"] / a["rank"]
        self.spec = _spec()

    def proba(self, texts: Sequence[str]) -> np.ndarray:
        out = np.zeros((len(texts), len(DEPARTMENTS)), dtype=np.float32)
        for i, text in enumerate(texts):
            idx = features(text, self.spec)
            x = self.emb[idx].mean(axis=0)
            ad = self.adapter
            if ad is not None:
                x = x + self.scale * (ad["emb_a.weight"][idx].mean(axis=0) @ ad["emb_b.weight"].T)
            h = x @ self.fc_w.T + self.fc_b
            if ad is not None:
                h = h + self.scale * ((x @ ad["fc_a.weight"].T) @ ad["fc_b.weight"].T)
            h = np.maximum(h, 0)
            z = h @ self.head_w.T + self.head_b
            if ad is not None:
                z = z + self.scale * ((h @ ad["head_a.weight"].T) @ ad["head_b.weight"].T) + ad["head_bias"]
            z = z - z.max()
            e = np.exp(z)
            out[i] = e / e.sum()
        return out
