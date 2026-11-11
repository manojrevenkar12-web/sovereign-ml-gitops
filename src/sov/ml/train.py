"""Training: the shared base, a LoRA adapter per authority, and a full fine-tune for comparison."""

from __future__ import annotations

import copy
import time
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import torch
from torch import nn

from sov.config import platform
from sov.ml.model import Adapter, FeatureSpec, Router, batch, load_arrays, to_arrays

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
INDEX = {d: i for i, d in enumerate(DEPARTMENTS)}


def spec() -> FeatureSpec:
    m = platform()["model"]
    return FeatureSpec(m["buckets"], m["char_ngrams"][0], m["char_ngrams"][1], m["word_bigrams"])


def new_router() -> Router:
    m = platform()["model"]
    torch.manual_seed(m["seed"])
    return Router(m["buckets"], m["dim"], m["hidden"], len(DEPARTMENTS))


def new_adapter() -> Adapter:
    m, a = platform()["model"], platform()["train"]["adapter"]
    torch.manual_seed(m["seed"] + 1)
    return Adapter(m["buckets"], m["dim"], m["hidden"], len(DEPARTMENTS), a["rank"], a["alpha"])


@dataclass
class Encoded:
    idx: list[torch.Tensor]
    offsets: list[torch.Tensor]
    y: list[torch.Tensor]


def _encode(texts: Sequence[str], labels: Sequence[str], bs: int, seed: int) -> Encoded:
    rng = np.random.default_rng(seed)
    order = rng.permutation(len(texts))
    sp = spec()
    enc = Encoded([], [], [])
    for i in range(0, len(order), bs):
        part = order[i : i + bs]
        idx, off = batch([texts[j] for j in part], sp)
        enc.idx.append(idx)
        enc.offsets.append(off)
        enc.y.append(torch.tensor([INDEX[labels[j]] for j in part]))
    return enc


def _fit(
    params: list[nn.Parameter],
    forward,
    texts,
    labels,
    epochs: int,
    lr: float,
    bs: int,
    wd: float = 0.0,
    class_weight: torch.Tensor | None = None,
) -> None:
    opt = torch.optim.Adam(params, lr=lr, weight_decay=wd)
    loss_fn = nn.CrossEntropyLoss(weight=class_weight)
    for epoch in range(epochs):
        enc = _encode(texts, labels, bs, seed=epoch)
        for idx, off, y in zip(enc.idx, enc.offsets, enc.y, strict=True):
            opt.zero_grad()
            loss = loss_fn(forward(idx, off), y)
            loss.backward()
            opt.step()


def train_base(texts: Sequence[str], labels: Sequence[str]) -> dict[str, np.ndarray]:
    cfg = platform()["train"]["base"]
    model = new_router()
    _fit(
        list(model.parameters()),
        lambda i, o: model(i, o),
        texts,
        labels,
        cfg["epochs"],
        cfg["lr"],
        cfg["batch"],
        cfg["weight_decay"],
    )
    return to_arrays(model)


def load_router(arrays: dict[str, np.ndarray]) -> Router:
    model = new_router()
    load_arrays(model, arrays)
    model.eval()
    return model


def train_adapter(
    base: dict[str, np.ndarray], texts: Sequence[str], labels: Sequence[str], critical: Sequence[str] = ()
) -> dict[str, np.ndarray]:
    """Critical departments (rare, but a miss is costly: hazard reports) are weighted up in the loss."""
    cfg = platform()["train"]["adapter"]
    model = load_router(base)
    for p in model.parameters():
        p.requires_grad_(False)
    adapter = new_adapter()
    weight = torch.ones(len(DEPARTMENTS))
    for c in critical:
        weight[INDEX[c]] = cfg["critical_weight"]
    _fit(
        list(adapter.parameters()),
        lambda i, o: model(i, o, adapter),
        texts,
        labels,
        cfg["epochs"],
        cfg["lr"],
        cfg["batch"],
        class_weight=weight,
    )
    return to_arrays(adapter)


def train_full(base: dict[str, np.ndarray], texts: Sequence[str], labels: Sequence[str]) -> dict[str, np.ndarray]:
    cfg = platform()["train"]["full"]
    model = copy.deepcopy(load_router(base))
    model.train()
    _fit(list(model.parameters()), lambda i, o: model(i, o), texts, labels, cfg["epochs"], cfg["lr"], cfg["batch"])
    return to_arrays(model)


def load_adapter(arrays: dict[str, np.ndarray]) -> Adapter:
    adapter = new_adapter()
    load_arrays(adapter, arrays)
    adapter.eval()
    return adapter


class Predictor:
    """Base plus an optional adapter, as served."""

    def __init__(self, base: dict[str, np.ndarray], adapter: dict[str, np.ndarray] | None = None):
        self.model = load_router(base)
        self.adapter = load_adapter(adapter) if adapter is not None else None
        self.spec = spec()

    @torch.no_grad()
    def proba(self, texts: Sequence[str]) -> np.ndarray:
        out = []
        for i in range(0, len(texts), 512):
            idx, off = batch(texts[i : i + 512], self.spec)
            out.append(torch.softmax(self.model(idx, off, self.adapter), dim=1).numpy())
        return np.concatenate(out) if out else np.zeros((0, len(DEPARTMENTS)))

    def predict(self, texts: Sequence[str]) -> list[str]:
        return [DEPARTMENTS[i] for i in self.proba(texts).argmax(axis=1)]

    def latency_ms(self, texts: Sequence[str], n: int = 300) -> dict[str, float]:
        times = []
        for t in list(texts)[:n]:
            start = time.perf_counter()
            self.proba([t])
            times.append((time.perf_counter() - start) * 1000)
        return {"p50": float(np.percentile(times, 50)), "p95": float(np.percentile(times, 95))}
