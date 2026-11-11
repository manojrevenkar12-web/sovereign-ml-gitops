"""Inquiry router: hashed n-gram bag -> hidden layer -> department, with LoRA adapters per authority.

The base model is shared by every authority. An authority's adapter is ~8% of the base's parameters and
holds what is local: its own words ("Kundenzentrum", "NHE"), and which department handles what there.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import torch
from torch import nn

from sov.ml.features import FeatureSpec, features


def batch(texts: Sequence[str], spec: FeatureSpec) -> tuple[torch.Tensor, torch.Tensor]:
    idx: list[int] = []
    offsets: list[int] = []
    for t in texts:
        offsets.append(len(idx))
        idx.extend(features(t, spec))
    return torch.tensor(idx, dtype=torch.long), torch.tensor(offsets, dtype=torch.long)


class Adapter(nn.Module):
    """LoRA on the embedding table, the hidden layer and the head, plus a head bias shift."""

    def __init__(self, buckets: int, dim: int, hidden: int, classes: int, rank: int, alpha: float):
        super().__init__()
        self.scale = alpha / rank
        self.emb_a = nn.EmbeddingBag(buckets, rank, mode="mean")
        self.emb_b = nn.Linear(rank, dim, bias=False)
        self.fc_a = nn.Linear(dim, rank, bias=False)
        self.fc_b = nn.Linear(rank, hidden, bias=False)
        self.head_a = nn.Linear(hidden, rank, bias=False)
        self.head_b = nn.Linear(rank, classes, bias=False)
        self.head_bias = nn.Parameter(torch.zeros(classes))
        nn.init.normal_(self.emb_a.weight, std=0.02)
        for b in (self.emb_b, self.fc_b, self.head_b):
            nn.init.zeros_(b.weight)

    def n_params(self) -> int:
        return sum(p.numel() for p in self.parameters())


class Router(nn.Module):
    def __init__(self, buckets: int, dim: int, hidden: int, classes: int):
        super().__init__()
        self.emb = nn.EmbeddingBag(buckets, dim, mode="mean")
        self.fc = nn.Linear(dim, hidden)
        self.head = nn.Linear(hidden, classes)
        nn.init.normal_(self.emb.weight, std=0.05)

    def forward(self, idx: torch.Tensor, offsets: torch.Tensor, adapter: Adapter | None = None) -> torch.Tensor:
        x = self.emb(idx, offsets)
        if adapter is not None:
            x = x + adapter.scale * adapter.emb_b(adapter.emb_a(idx, offsets))
        h = self.fc(x)
        if adapter is not None:
            h = h + adapter.scale * adapter.fc_b(adapter.fc_a(x))
        h = torch.relu(h)
        out = self.head(h)
        if adapter is not None:
            out = out + adapter.scale * adapter.head_b(adapter.head_a(h)) + adapter.head_bias
        return out

    def n_params(self) -> int:
        return sum(p.numel() for p in self.parameters())


def to_arrays(module: nn.Module) -> dict[str, np.ndarray]:
    """Weights as plain arrays: artifacts are .npz files, never pickles."""
    return {k: v.detach().cpu().numpy().astype(np.float16) for k, v in module.state_dict().items()}


def load_arrays(module: nn.Module, arrays: dict[str, np.ndarray]) -> None:
    module.load_state_dict({k: torch.from_numpy(np.asarray(v, dtype=np.float32)) for k, v in arrays.items()})
