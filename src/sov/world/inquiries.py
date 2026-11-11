"""Simulated citizen inquiries. THIS MODULE HOLDS THE TRUTH.

Decision code (src/sov/ml, src/sov/pii, src/sov/serve, src/sov/tenancy) never imports it. The pipeline
receives `Inquiry.text` and `Inquiry.handler_label` (what a case handler filed it under), exactly as an
export from a ticket system would give them. `true_dept` and `pii` spans exist only for scoring.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

import yaml

from sov.config import ROOT
from sov.world import pii as piigen


@lru_cache
def world() -> dict[str, Any]:
    return yaml.safe_load((ROOT / "config" / "world.yaml").read_text(encoding="utf-8"))


@dataclass
class Inquiry:
    text: str
    handler_label: str
    true_dept: str
    topic: str
    tenant: str
    pii: list[piigen.Span] = field(default_factory=list)


def tenant_spec(tenant: str) -> dict[str, Any]:
    w = world()
    if tenant == "generic":
        return {
            "office": w["generic"]["office"],
            "pass": w["generic"]["pass"],
            "waste": w["generic"]["waste"],
            "overrides": {},
            "weights": {},
        }
    if tenant in w["tenants"]:
        return w["tenants"][tenant]
    return w["heldout_tenants"][tenant]


def routing(tenant: str, after_reorg: bool = True) -> dict[str, str]:
    """True topic -> department map for an authority."""
    w = world()
    spec = tenant_spec(tenant)
    out = {t: v["dept"] for t, v in w["topics"].items()}
    out.update(spec.get("overrides", {}))
    reorg = spec.get("reorg")
    if reorg:
        out[reorg["topic"]] = reorg["after"] if after_reorg else reorg["before"]
    return out


def _typo(word: str, rng: random.Random) -> str:
    if len(word) < 4:
        return word
    i = rng.randrange(len(word) - 1)
    return word[:i] + word[i + 1] + word[i] + word[i + 2 :]


class _Builder:
    """Concatenates parts and remembers where personal data landed."""

    def __init__(self) -> None:
        self.text = ""
        self.spans: list[piigen.Span] = []

    def add(self, part: str, sep: str = " ") -> None:
        if not part:
            return
        self.text += (sep if self.text else "") + part

    def add_pii(self, template: str, values: dict[str, tuple[str, str]], sep: str = " ") -> None:
        """template like 'mein name ist {name}'; values: key -> (kind, value)."""
        if self.text:
            self.text += sep
        pos = 0
        while pos < len(template):
            start = template.find("{", pos)
            if start < 0:
                self.text += template[pos:]
                break
            self.text += template[pos:start]
            end = template.index("}", start)
            kind, value = values[template[start + 1 : end]]
            begin = len(self.text)
            self.text += value
            self.spans.append(piigen.Span(kind, begin, len(self.text), value))
            pos = end + 1


PII_SENTENCES = [
    ("mein name ist {name}", ["name"]),
    ("ich wohne in der {address}", ["address"]),
    ("meine iban ist {iban}", ["iban"]),
    ("bitte rückruf unter {phone}", ["phone"]),
    ("sie erreichen mich per mail: {email}", ["email"]),
    ("steuer-id {steuerid}", ["steuerid"]),
    ("geb. {dob}", ["dob"]),
    ("antragsteller: {name}, {address}", ["name", "address"]),
    # how people actually write, without the cue words a rule can anchor on
    ("{name} hier", ["name"]),
    ("viele grüße {first}", ["first"]),
    ("wir wohnen {square}", ["square"]),
    ("tel {phone}", ["phone"]),
]


def generate(tenant: str, n: int, seed: int, after_reorg: bool = True, vocab_from: str | None = None) -> list[Inquiry]:
    """`vocab_from` lets a wrong-tenant export use another authority's wording and routing."""
    w = world()
    rng = random.Random(f"{tenant}:{seed}:{after_reorg}:{vocab_from}")
    src = vocab_from or tenant
    spec = tenant_spec(src)
    route = routing(src, after_reorg)
    topics = list(w["topics"])
    weights = [spec.get("weights", {}).get(t, w["topics"][t]["weight"]) for t in topics]
    depts = w["departments"]
    out: list[Inquiry] = []
    for _ in range(n):
        topic = rng.choices(topics, weights)[0]
        b = _Builder()
        b.add(rng.choice(w["openers"]))
        phrase = rng.choice(w["topics"][topic]["phrases"]).format(
            office=spec["office"], **{"pass": spec["pass"]}, waste=spec["waste"]
        )
        if rng.random() < w["typo_rate"]:
            words = phrase.split()
            k = rng.randrange(len(words))
            words[k] = _typo(words[k], rng)
            phrase = " ".join(words)
        b.add(phrase)
        if rng.random() < 0.35:
            b.add(rng.choice(w["local_refs"]).format(office=spec["office"]))
        if rng.random() < w["two_topic_rate"]:
            other = rng.choice([t for t in topics if t != topic])
            b.add(
                "außerdem noch kurz: "
                + rng.choice(w["topics"][other]["phrases"])
                .format(office=spec["office"], **{"pass": spec["pass"]}, waste=spec["waste"])
                .split(" und ")[0],
                sep=". ",
            )
        if rng.random() < w["pii_rate"]:
            template, kinds = rng.choice(PII_SENTENCES)
            values = {k: piigen.make(k, rng) for k in kinds}
            b.add_pii(template, values, sep=". ")
        b.add(rng.choice(w["closers"]), sep=". ")
        true = route[topic]
        label = true
        if rng.random() < w["handler_label_noise"]:
            label = rng.choice([d for d in depts if d != true])
        out.append(Inquiry(b.text, label, true, topic, tenant, b.spans))
    return out


def generic_corpus(n: int, seed: int) -> list[Inquiry]:
    """What a platform team can collect before any authority joins: generic wording and routing."""
    return generate("generic", n, seed)


def archive(tenant: str, label: str, n: int, seed: int, after_reorg: bool = True) -> list[Inquiry]:
    """Older tickets a case handler filed under `label`: how a team tops up a rare critical class.
    Selection uses the handler's label only, as a real archive query would."""
    out: list[Inquiry] = []
    batch_seed = seed
    while len(out) < n:
        pool = generate(tenant, 2000, 10_000 + batch_seed, after_reorg=after_reorg)
        out += [q for q in pool if q.handler_label == label]
        batch_seed += 1
    return out[:n]


def with_archive(
    inq: list[Inquiry], tenant: str, critical: list[str], need: int, seed: int, after_reorg: bool = True
) -> list[Inquiry]:
    """Top up every critical class to `need` examples from the archive."""
    out = list(inq)
    for c in critical:
        have = sum(q.handler_label == c for q in out)
        if have < need:
            out += archive(tenant, c, need - have, seed, after_reorg)
    return out
