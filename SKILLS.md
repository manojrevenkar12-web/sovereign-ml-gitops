# Repeatable tasks

## Onboard an authority

1. Copy a similar file in `tenants/`, then change `name`, `display_name`, `contact`, `model.critical`,
   `fine_tune.where` and the groups. Leave `model.base` and `model.adapter` as `null`.
2. `python scripts/scaffold.py && python scripts/isolation_check.py`
3. `pytest -q tests/test_platform_files.py`
4. Open the merge request. The authority goes live only when a release pins an adapter.

## Release adapters

1. `python scripts/publish.py` (or, in GitLab, the scheduled `fine-tune` matrix and then `release-mr`).
2. Read `reports/releases/<name>.json`. A held release says which check failed and by how much.
3. `python scripts/report.py` to refresh the dashboard and the README.

## Add a personal-data rule

1. Add a failing example to `tests/test_redactor.py`.
2. Change `config/pii_rules.yaml`, or `src/sov/pii/engine.lua` if the engine needs a new kind of matcher.
3. `python scripts/gen_redactor.py && pytest -q tests/test_redactor.py && python scripts/pii_eval.py`.
   Check precision as well as recall: audit lines must stay readable.

## Investigate an alert

Follow `docs/runbook.md`. Every alert's `runbook_url` points to its section.
