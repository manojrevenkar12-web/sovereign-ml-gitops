.PHONY: test lint generated evals report web e2e

test:
	pytest -q

lint:
	ruff check . && ruff format --check .

generated:
	python scripts/gen_redactor.py
	python scripts/scaffold.py

evals:
	python scripts/finetune_eval.py
	python scripts/release_eval.py
	python scripts/pii_eval.py
	python scripts/isolation_check.py

report:
	python scripts/report.py

web:
	cd web && npm ci && npm test && npm run build

e2e:
	docker build -t sov-api:e2e .
	python scripts/e2e_env.py /tmp/sov-tampered > .env
	docker compose --env-file .env -f deploy/compose/e2e.yaml up -d
	pytest -m e2e tests/e2e
