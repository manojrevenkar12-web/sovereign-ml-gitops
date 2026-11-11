# The held-out run

**What was held out**

- **An authority:** `stadt-ostmark`. It has its own routing, its own words and its own departments, and
  nobody looked at its data while the pipeline, the gate or the rules were built.
- **Five log formats** the redaction rules were not written against:
  - JSON with `\u` escapes;
  - "Surname, First name" CSV rows;
  - phone numbers in brackets;
  - lower-case IBANs without spaces;
  - single-digit birth dates.

**How it was run.** `config/heldout.lock` pinned the gate, the training code, `platform.toml` and the
redaction rules, with their sha256 hashes, before the run. `scripts/heldout.py` refuses to run if any of
those files changed, and refuses to run a second time. It ran once; `reports/heldout.json` is that run.

After the run, `ruff format` rewrapped lines in five pinned Python files; no statement changed. The lock
records the hashes from before and after, and the evidence that nothing changed:
`scripts/publish.py --only stadt-weidenbach --dry-run` reproduces the pinned adapter digest byte for byte.

## Onboarding an unseen authority

| | Accuracy on Ostmark's inquiries (true department) |
|---|---|
| Shared base only | 83.0% |
| Base + Ostmark's adapter | **91.4%** |
| Development authorities, adapter, mean of 9 runs | 94.3% |

The gate promoted the adapter:

- the training data was pseudonymised;
- the bound against the base was +6.0 points;
- hazard-report recall was 91% on validation and 87% on the truth.

Ostmark is 3 points below the development authorities. Its adapter had to learn, from 400 inquiries, that
four topics are handled by a different department there.

## Log formats nobody wrote rules for

| Format | Personal data found |
|---|---|
| JSON with `\u` escapes | 86% |
| CSV export, "Surname, First name" | 33% |
| Lower-case IBAN, `holder=` | 39% |
| Single-digit birth dates | 0% |
| Audit lines (no personal data) | 5 false finds |
| **All** | **35.4%** (precision 99.8%) |

By kind:

| Kind | Found |
|---|---|
| Email, tax id | 100% |
| Address | 97% |
| Name | 43% |
| Phone | 8% |
| Birth date | 4% |
| IBAN | 4% |

**What failed.** Every miss is a format assumption:

- IBANs are assumed upper case;
- phone numbers are assumed to start with `0` or `+49`, not `(030)`;
- birth dates are assumed to have two digits per part;
- names are assumed to follow a cue word or a known first name, not to come surname-first.

**What this means for the platform.** A rule-based filter is only as good as the formats it has seen. The
99.4% on development formats does not carry over to a new service with new log habits. Two changes follow,
and neither is in this repository yet:

1. **A merge-request check for new services.** A new service contributes sample log lines (synthetic
   citizens). CI runs them through `redact.lua`, and the merge request fails while any seeded value
   survives. This catches format drift where it starts.
2. **Rules for the five formats above,** written once (1) exists, then re-scored on a new held-out set.
   Writing them now and re-running this set would turn the held-out set into a development set.
