# Working in this repository

## Fast feedback

- `pytest -q` (30 tests, about 10 s) and `ruff check . && ruff format --check .` before every commit.
- `python scripts/gen_redactor.py --check` and `python scripts/scaffold.py --check` whenever you change
  `config/pii_rules.yaml`, `src/sov/pii/engine.lua`, `tenants/` or `infra/templates/`.
- `cd web && npm test` for the dashboard.

## Invariants

- **Truth stays in the world.** Only `src/sov/world/`, `src/sov/evals.py` and `scripts/` read
  `config/world.yaml` or an inquiry's `true_dept` and `pii` spans. Nothing under `src/sov/ml`, `pii`,
  `serve` or `tenancy` imports `sov.world`.
- **One definition of personal data.** Rules live in `config/pii_rules.yaml`. `deploy/fluent-bit/redact.lua`
  is generated, and the pipeline runs the same file. Never hand-edit the generated Lua.
- **One file per authority.** Everything authority-specific is derived from `tenants/<name>.yaml`. Only the
  release step (`scripts/publish.py`) changes `model.base` and `model.adapter`.
- **Digests, not tags.** Model artifacts are referenced by `sha256:` everywhere. A digest is never edited by
  hand to make a pod start.
- **The gate is not moved to pass a release.** Thresholds live in `config/platform.toml`. Changing one needs
  a written reason in `docs/decisions.md` and two reviews.
- **Settings in config.** No threshold, size or path is written in code.
- **Reports are generated.** `reports/*.json`, `web/public/data.json` and the README results block come from
  scripts. Never type a number into them.

## The held-out rule

`stadt-ostmark` and `heldout_log_corpus` are the held-out set. They ran once (`reports/heldout.json`,
`config/heldout.lock`). Do not tune anything against them. New rules for the formats they exposed need a new
held-out set (see `docs/heldout.md`).
