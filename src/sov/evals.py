"""Scoring against the truth. Only scripts/ and tests import this module; nothing that decides does."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from sov.world.pii import KINDS, LogLine, Span


def accuracy(pred: Sequence[str], truth: Sequence[str]) -> float:
    return float(np.mean([p == t for p, t in zip(pred, truth, strict=True)]))


def score_redaction(lines: Sequence[LogLine], found: Sequence[Sequence[tuple[str, int, int]]]) -> dict:
    """An instance is caught when one or more found spans cover all of its characters.
    A found span is correct when it overlaps a true instance."""
    per = {k: {"instances": 0, "caught": 0} for k in KINDS}
    produced = correct = 0
    for line, spans in zip(lines, found, strict=True):
        for t in line.spans:
            per[t.kind]["instances"] += 1
            covered = set()
            for _, s, e in spans:
                covered.update(range(max(s, t.start), min(e, t.end)))
            if len(covered) == t.end - t.start:
                per[t.kind]["caught"] += 1
        for _, s, e in spans:
            produced += 1
            correct += any(s < t.end and e > t.start for t in line.spans)
    inst = sum(v["instances"] for v in per.values())
    caught = sum(v["caught"] for v in per.values())
    return {
        "recall": caught / max(1, inst),
        "precision": correct / max(1, produced),
        "instances": inst,
        "caught": caught,
        "found": produced,
        "false_finds": produced - correct,
        "by_kind": {
            k: {**v, "recall": v["caught"] / v["instances"] if v["instances"] else None} for k, v in per.items()
        },
    }


def spans_of(line: LogLine) -> list[Span]:
    return line.spans
