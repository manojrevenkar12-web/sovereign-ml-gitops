"""Personal data the simulated citizens write, and the log lines it leaks into. THE TRUTH.

Every value is generated with valid check digits (IBAN mod 97, tax id ISO 7064), so a redactor that
validates check digits gets no free pass from fake-looking data.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from urllib.parse import quote

KINDS = ["name", "address", "iban", "phone", "email", "steuerid", "dob", "ip"]


@dataclass(frozen=True)
class Span:
    kind: str
    start: int
    end: int
    value: str


def _names() -> dict[str, list[str]]:
    from sov.world.inquiries import world

    return world()["names"]


def iban(rng: random.Random, spaced: bool = True) -> str:
    bban = f"{rng.randrange(10**7, 10**8)}{rng.randrange(10**9, 10**10)}"
    numeric = int(bban + "131400")  # D=13 E=14 00
    check = 98 - numeric % 97
    raw = f"DE{check:02d}{bban}"
    if not spaced:
        return raw
    return " ".join(raw[i : i + 4] for i in range(0, len(raw), 4))


def steuer_check(digits: str) -> int:
    product = 10
    for ch in digits[:10]:
        s = (int(ch) + product) % 10
        if s == 0:
            s = 10
        product = (s * 2) % 11
    check = 11 - product
    return 0 if check == 10 else check


def steuerid(rng: random.Random) -> str:
    # ten digits, first not zero, exactly one digit repeated (twice), as issued since 2016
    pool = list(range(10))
    rng.shuffle(pool)
    body = pool[:9]
    while body[0] == 0:
        rng.shuffle(body)
    body.insert(rng.randrange(1, 10), rng.choice(body[1:]))
    digits = "".join(map(str, body[:10]))
    return digits + str(steuer_check(digits))


def phone(rng: random.Random, style: int | None = None) -> str:
    style = rng.randrange(4) if style is None else style
    if style == 0:
        return f"+49 {rng.choice(['30', '40', '89', '231', '351'])} {rng.randrange(1000000, 99999999)}"
    if style == 1:
        return f"0{rng.choice(['151', '160', '176', '172'])} {rng.randrange(10**7, 10**8)}"
    if style == 2:
        return f"0{rng.choice(['30', '40', '231'])}/{rng.randrange(100000, 9999999)}"
    return f"0{rng.choice(['176', '152'])}-{rng.randrange(10**7, 10**8)}"


def name(rng: random.Random) -> str:
    n = _names()
    return f"{rng.choice(n['first']).title()} {rng.choice(n['last']).title()}"


def address(rng: random.Random) -> str:
    n = _names()
    street = rng.choice([s for s in n["streets"] if not s.startswith("am ")])
    return f"{street.title()} {rng.randrange(1, 140)}"


def email(rng: random.Random) -> str:
    n = _names()
    first = rng.choice(n["first"])
    last = rng.choice(n["last"]).replace("ü", "ue").replace("ö", "oe").replace("ı", "i")
    return f"{first}.{last}{rng.choice(['', '82', '.nh'])}@{rng.choice(['web.de', 'gmx.net', 'posteo.de', 'mail.example.org'])}"


def dob(rng: random.Random) -> str:
    return f"{rng.randrange(1, 29):02d}.{rng.randrange(1, 13):02d}.{rng.randrange(1940, 2006)}"


def ip(rng: random.Random) -> str:
    return f"{rng.choice([84, 91, 178, 217])}.{rng.randrange(256)}.{rng.randrange(256)}.{rng.randrange(1, 255)}"


def first_lower(rng: random.Random) -> str:
    return rng.choice(_names()["first"])


def square(rng: random.Random) -> str:
    return f"{rng.choice(['am markt', 'an der kirche', 'im winkel'])} {rng.randrange(1, 40)}"


def make(kind: str, rng: random.Random) -> tuple[str, str]:
    if kind == "first":
        return "name", first_lower(rng)
    if kind == "square":
        return "address", square(rng)
    return kind, {
        "name": name,
        "address": address,
        "iban": iban,
        "phone": phone,
        "email": email,
        "steuerid": steuerid,
        "dob": dob,
        "ip": ip,
    }[kind](rng)


# ---------------------------------------------------------------------------------------- log lines


@dataclass
class LogLine:
    source: str
    text: str
    spans: list[Span]


class _Line:
    def __init__(self) -> None:
        self.text = ""
        self.spans: list[Span] = []

    def lit(self, s: str) -> _Line:
        self.text += s
        return self

    def pii(self, kind: str, value: str) -> _Line:
        start = len(self.text)
        self.text += value
        self.spans.append(Span(kind, start, len(self.text), value))
        return self


def _ts(rng: random.Random) -> str:
    return (
        f"2026-11-{rng.randrange(1, 11):02d}T{rng.randrange(24):02d}:{rng.randrange(60):02d}:{rng.randrange(60):02d}Z"
    )


def _inquiry_line(rng: random.Random, tenant: str) -> _Line:
    from sov.world.inquiries import generate

    inq = generate(tenant, 1, rng.randrange(10**9))[0]
    ln = _Line().lit(
        f'{{"ts":"{_ts(rng)}","level":"ERROR","svc":"inquiry-api","tenant":"{tenant}",'
        f'"msg":"validation failed","body":"'
    )
    base = len(ln.text)
    ln.text += inq.text
    ln.spans += [Span(s.kind, base + s.start, base + s.end, s.value) for s in inq.pii]
    ln.lit('"}')
    return ln


def _ingress(rng: random.Random) -> _Line:
    ln = (
        _Line()
        .pii("ip", ip(rng))
        .lit(f" - - [{rng.randrange(1, 11):02d}/Nov/2026:10:{rng.randrange(60):02d}:01 +0100] ")
    )
    choice = rng.randrange(3)
    if choice == 0:
        e = email(rng)
        ln.lit('"GET /api/v1/termine?email=').pii("email", quote(e, safe="")).lit('&lang=de HTTP/1.1" 200 ')
    elif choice == 1:
        ln.lit('"GET /api/v1/rueckruf?tel=').pii("phone", quote(phone(rng, 1), safe="")).lit(' HTTP/1.1" 204 ')
    else:
        ln.lit(f'"GET /api/v1/status/{rng.randrange(10**5)} HTTP/1.1" 200 ')
    return ln.lit(str(rng.randrange(100, 9000)))


def _traceback(rng: random.Random) -> _Line:
    ln = _Line().lit(f"{_ts(rng)} ERROR payment-export KeyError: 'bic' while processing payload={{'name': '")
    ln.pii("name", name(rng)).lit("', 'iban': '").pii("iban", iban(rng)).lit(f"', 'amount': {rng.randrange(20, 900)}}}")
    return ln


def _form(rng: random.Random) -> _Line:
    ln = _Line().lit(f"{_ts(rng)} WARN form-service draft saved: Antragsteller: ").pii("name", name(rng))
    ln.lit(", geb. ").pii("dob", dob(rng)).lit(", Steuer-ID ").pii("steuerid", steuerid(rng))
    return ln


def _audit(rng: random.Random, tenants: list[str]) -> _Line:
    """No personal data, but plenty that looks like it: digests, case numbers, pod IPs in versions."""
    h = "".join(rng.choice("0123456789abcdef") for _ in range(64))
    case = "".join(rng.choice("0123456789") for _ in range(11))
    return _Line().lit(
        f"{_ts(rng)} INFO release-controller tenant={rng.choice(tenants)} action=promote "
        f"adapter=sha256:{h} vorgang={case} chart=sov-model-1.{rng.randrange(9)}.{rng.randrange(20)} "
        f"az=63-2026-{rng.randrange(10**5):05d} latency_ms={rng.randrange(3, 40)}"
    )


def log_corpus(n: int, seed: int, tenants: list[str]) -> list[LogLine]:
    rng = random.Random(f"logs:{seed}")
    out: list[LogLine] = []
    for _ in range(n):
        r = rng.random()
        if r < 0.35:
            ln, src = _inquiry_line(rng, rng.choice(tenants)), "app-json"
        elif r < 0.55:
            ln, src = _ingress(rng), "ingress"
        elif r < 0.65:
            ln, src = _traceback(rng), "traceback"
        elif r < 0.75:
            ln, src = _form(rng), "form"
        else:
            ln, src = _audit(rng, tenants), "audit"
        out.append(LogLine(src, ln.text, ln.spans))
    return out


# ------------------------------------------------------------ held-out formats (never used to build rules)


def heldout_log_corpus(n: int, seed: int, tenants: list[str]) -> list[LogLine]:
    """Formats the rules were not written against: ASCII-escaped JSON, 'Nachname, Vorname' exports,
    phone numbers with brackets, unspaced lower-case IBANs, single-digit birth days."""
    rng = random.Random(f"heldout-logs:{seed}")
    out: list[LogLine] = []
    for _ in range(n):
        r = rng.random()
        if r < 0.25:
            ln = _inquiry_line(rng, rng.choice(tenants))
            # re-encode as ASCII-escaped JSON the way json.dumps does by default
            escaped = _Line()
            pos = 0
            for s in ln.spans:
                escaped.lit(json.dumps(ln.text[pos : s.start])[1:-1])
                escaped.pii(s.kind, json.dumps(s.value)[1:-1])
                pos = s.end
            escaped.lit(json.dumps(ln.text[pos:])[1:-1])
            out.append(LogLine("app-json-ascii", escaped.text, escaped.spans))
            continue
        if r < 0.45:
            first, last = name(rng).split(" ")
            ln = _Line().lit(f"{_ts(rng)} INFO csv-export row=").pii("name", f"{last}, {first}")
            ln.lit(";").pii("address", address(rng)).lit(";").pii(
                "phone", f"({rng.choice(['030', '0231'])}) {rng.randrange(10**6, 10**7)}"
            )
            out.append(LogLine("csv-export", ln.text, ln.spans))
            continue
        if r < 0.65:
            ln = _Line().lit(f"{_ts(rng)} DEBUG sepa-mandate iban=").pii("iban", iban(rng, spaced=False).lower())
            ln.lit(" holder=").pii("name", name(rng))
            out.append(LogLine("sepa-debug", ln.text, ln.spans))
            continue
        if r < 0.8:
            ln = (
                _Line()
                .lit(f"{_ts(rng)} WARN form-service geboren am ")
                .pii("dob", f"{rng.randrange(1, 10)}.{rng.randrange(1, 10)}.{rng.randrange(1950, 2005)}")
            )
            ln.lit(" in ").lit(rng.choice(["lindenau", "oberdorf"]))
            out.append(LogLine("form-v2", ln.text, ln.spans))
            continue
        out.append(LogLine("audit", _audit(rng, tenants).text, []))
    return out
