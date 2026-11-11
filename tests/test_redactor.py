import random
import subprocess
import sys

from sov.config import ROOT
from sov.pii.redact import redact, redact_record
from sov.world import pii


def kinds(text: str) -> list[str]:
    return [f.kind for f in redact(text)[1]]


def test_generated_filter_is_fresh():
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "gen_redactor.py"), "--check"], capture_output=True)
    assert r.returncode == 0, r.stderr.decode()


def test_valid_identifiers_are_found_and_invalid_ones_are_not():
    rng = random.Random(1)
    iban = pii.iban(rng)
    broken = iban[:-1] + str((int(iban[-1]) + 1) % 10)
    assert kinds(f"iban {iban} ok") == ["iban"]
    assert kinds(f"iban {broken} ok") == []
    tax = pii.steuerid(rng)
    assert kinds(f"steuer-id {tax}") == ["steuerid"]
    assert kinds(f"steuer-id {tax[:-1]}{(int(tax[-1]) + 1) % 10}") == []


def test_cue_words_names_addresses_and_dates():
    out, found = redact("antragsteller: Jonas Becker, Bahnhofstraße 12, geb. 01.02.1990")
    assert out == "antragsteller: <name>, <address>, geb. <dob>"
    assert [f.kind for f in found] == ["name", "address", "dob"]
    assert kinds("viele grüße anna") == ["name"]
    assert kinds("wir wohnen am markt 3") == ["address"]
    assert kinds("termin am 01.02.2026") == []  # a date is only personal with a birth cue


def test_url_encoded_contacts_in_access_logs():
    line = '84.12.3.4 - - "GET /api/v1/termine?email=anna.mueller%40web.de&tel=0151%2023456789 HTTP/1.1"'
    assert kinds(line) == ["ip", "email", "phone"]


def test_audit_lines_stay_readable():
    line = (
        "2026-11-04T10:00:00Z INFO release-controller tenant=stadt-nordhafen action=promote "
        "adapter=sha256:" + "ab" * 32 + " chart=sov-model-1.4.0 az=63-2026-00123 latency_ms=12"
    )
    assert redact(line)[0] == line


def test_offsets_are_character_positions_with_umlauts():
    text = "grüße, mein name ist Jürgen Öztürk und so"
    out, found = redact(text)
    assert text[found[0].start : found[0].end] == "Jürgen Öztürk"
    assert out == "grüße, mein name ist <name> und so"


def test_fluent_bit_callback_marks_records():
    code, rec = redact_record({"log": "mein name ist Anna Schmidt", "kubernetes": {"pod": "x"}})
    assert code == 2
    assert rec["log"] == "mein name ist <name>"
    assert rec["pii_redactions"] == 1
    code, rec = redact_record({"log": "nothing personal here"})
    assert code == 0


def test_log_corpus_recall_on_development_formats():
    from sov.evals import score_redaction

    lines = pii.log_corpus(600, 5, ["stadt-nordhafen", "kreis-lindenau"])
    s = score_redaction(lines, [[(f.kind, f.start, f.end) for f in redact(ln.text)[1]] for ln in lines])
    assert s["recall"] > 0.97
    assert s["precision"] > 0.99
