# MuGuard backend

FastAPI app: stores documents encrypted in PostgreSQL, hides personal data in them (regex layer plus
the T1 model through Mubit), streams the scan to the browser, answers questions about the redacted
text and returns a truly redacted file. Python 3.12/3.13, managed with uv.

## Run

```bash
python3 scripts/local_db.py start                                   # from the repo root: local PostgreSQL
uv run --directory backend --env-file ../.env uvicorn app.main:app --port 8000
```

Settings come from the environment, then `backend/.env`, then the root `.env` (see
`app/core/config.py` and `.env.example`). Without a Mubit key the app runs on the regex layer only.

## Check

```bash
cd backend
uv run --env-file ../.env pytest -q                 # PostgreSQL tests need TEST_DATABASE_URL
uv run ruff check app tests
uv run ruff format --check app tests
uv run mypy
```

## Layout

```
app/main.py      create_app()           app/core/       settings, logging, errors, security, crypto, db
app/api.py       router registry        app/modules/    auth, documents, scan, corrections, ask, samples, files
app/redaction/   detection, placeholders, PDF output      app/llm/   T1 and T2 through Mubit
app/ingest/      OCR (Apple Vision) and PDF text layers   migrations/   immutable SQL
```

[docs/architecture.md](docs/architecture.md) explains the layers, the rules inside a module, the
decisions behind them, and how the API contract is protected.
