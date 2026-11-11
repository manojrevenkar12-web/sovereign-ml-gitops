"""Hashed n-gram features. No torch here: the serving image imports this module and numpy only."""

from __future__ import annotations

import re
import zlib
from dataclasses import dataclass

TOKEN = re.compile(r"[\wäöüß]+", re.UNICODE)


@dataclass(frozen=True)
class FeatureSpec:
    buckets: int
    char_min: int
    char_max: int
    bigrams: bool


def features(text: str, spec: FeatureSpec) -> list[int]:
    words = TOKEN.findall(text.lower())
    feats = [f"w:{w}" for w in words]
    if spec.bigrams:
        feats += [f"b:{a}_{b}" for a, b in zip(words, words[1:], strict=False)]
    for w in words:
        padded = f"<{w}>"
        for n in range(spec.char_min, spec.char_max + 1):
            feats += [f"c:{padded[i : i + n]}" for i in range(max(1, len(padded) - n + 1))]
    if not feats:
        feats = ["<empty>"]
    return [zlib.crc32(f.encode("utf-8")) % spec.buckets for f in feats]
