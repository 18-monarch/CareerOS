PYTHON ?= python3
VENV = .venv/bin
.PHONY: install migrate seed api web test lint build verify
install:
	$(PYTHON) -m venv .venv
	$(VENV)/pip install -r requirements-dev.lock
	$(VENV)/pip install --no-deps -e .
	cd apps/web && npm ci
migrate:
	$(VENV)/alembic upgrade head
seed:
	$(VENV)/python -m careeros.seed
api:
	$(VENV)/uvicorn careeros.main:app --reload --host 127.0.0.1 --port 8000
web:
	cd apps/web && npm run dev
lint:
	$(VENV)/ruff check apps/api apps/worker
	$(VENV)/ruff format --check apps/api apps/worker
	cd apps/web && npm run lint && npm run typecheck
test:
	$(VENV)/pytest -q
	cd apps/web && npm run test
build:
	cd apps/web && npm run build
verify: lint test build
