# MuGuard task runner. `make help` lists the targets; run them from the repository root.
# Needs uv, Node and npm; `make db` also needs PostgreSQL 16+ binaries on PATH.

.DEFAULT_GOAL := help

# Pass the root .env to the backend when it exists (`make setup` creates it from .env.example).
ENV_FILE := $(if $(wildcard .env),--env-file ../.env,)
# Python for the root scripts/ and the training/ tools that share requirements.txt.
PYTHON ?= 3.12
PY := uv run --no-project --python $(PYTHON) --with-requirements requirements.txt python

.PHONY: help setup db dev backend frontend demo-servers demo-backend demo-mock demo-frontend \
        test test-app test-backend test-frontend test-training lint build

help: ## List the targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-15s %s\n", $$1, $$2}'

setup: ## Create .env if missing, install backend and frontend dependencies
	test -f .env || cp .env.example .env
	cd backend && uv sync --frozen
	npm --prefix frontend ci

db: ## Start the local PostgreSQL and write its settings into .env
	python3 scripts/local_db.py start

dev: ## Run backend (:8000) and frontend (:5173) together; open http://127.0.0.1:5173/app
	$(MAKE) -j2 backend frontend

backend: ## Run the FastAPI backend with reload on :8000
	cd backend && uv run $(ENV_FILE) uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

frontend: ## Run the Vite dev server on :5173
	npm --prefix frontend run dev -- --host 127.0.0.1 --port 5173

demo-servers: ## Servers for the demo video: backend :8002, mock stream :8010, frontend :5174
	$(MAKE) -j3 demo-backend demo-mock demo-frontend

demo-backend:
	cd backend && uv run $(ENV_FILE) uvicorn app.main:app --port 8002

demo-mock:
	MOCK_ERROR=none MOCK_BACKEND=$${VEIL_DEMO_BACKEND:-http://127.0.0.1:8002} node frontend/scripts/mock-stream.mjs

demo-frontend:
	cd frontend && VEIL_API=$${VEIL_DEMO_API:-http://127.0.0.1:8010} npx vite --port 5174 --strictPort

test: test-app test-training ## Run every test suite

test-app: test-backend test-frontend ## Tests of the running app

test-backend: ## Backend tests, ingestion and OCR included (database tests skip without TEST_DATABASE_URL)
	cd backend && uv run $(ENV_FILE) pytest -q

test-frontend: ## Frontend unit tests (Vitest)
	npm --prefix frontend test

# The rewrite and review tests run separately: both import helpers from a module named conftest.
test-training: ## Dataset and evaluation tooling tests (no network, no model calls)
	cd training/evalkit && uv run pytest -q
	$(PY) -m pytest -q training/rewrite/tests
	$(PY) -m pytest -q training/review_redaction/tests
	cd training/datagen && uv run pytest -q
	cd training/dataconv && uv run pytest -q

lint: ## Frontend type-check, and Python syntax errors and undefined names
	cd frontend && npx tsc --noEmit -p .
	uvx ruff check --select E9,F63,F7,F82 .

build: ## Production build of the frontend
	npm --prefix frontend run build
