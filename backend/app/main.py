"""MuGuard API: upload or paste, redact through Mubit, review, ask about it, download the redacted file.

Run from backend/: uv run --env-file ../.env uvicorn app.main:app --reload --port 8000
Documents and redactions persist encrypted in PostgreSQL; document text is never logged.

Layers, each importing only the ones below it:
  api/           routes, request and response shapes, dependencies, middleware
  services/      what the app does: ingest, scans, review, chat, samples, auth
  repositories/  SQL, over a pooled database (db/) with encrypted payloads
  domain/, llm/  redaction logic and the Mubit model calls, with no web or database code
"""

from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager

import psycopg
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import middleware
from .api.routers import auth, chat, documents, health, samples, scans
from .core.config import Config
from .core.log import log
from .llm.models import Models
from .llm.settings import describe, load_settings
from .repositories import Storage


@asynccontextmanager
async def lifespan(app: FastAPI):
    storage = Storage.from_env()
    try:
        storage.db.migrate()
    except psycopg.Error:
        storage.db.close()
        raise RuntimeError("PostgreSQL is unavailable. Check DATABASE_URL and start the database.") from None
    app.state.storage = storage
    try:
        yield
    finally:
        storage.db.close()


def create_app(config: Config | None = None, models: Models | None = None) -> FastAPI:
    config = config or Config.from_env()
    if models is None:
        settings = load_settings()
        models = Models.from_settings(settings)
        log.info(describe(settings, models.key_source))
    app = FastAPI(title="MuGuard", lifespan=lifespan)
    app.state.config = config
    app.state.models = models
    app.state.scan_executor = ThreadPoolExecutor(max_workers=config.scan_workers, thread_name_prefix="scan")
    app.add_middleware(CORSMiddleware, allow_origins=list(config.cors_origins), allow_methods=["*"],
                       allow_headers=["*"], allow_credentials=True)
    middleware.install(app)
    for module in (health, auth, documents, scans, chat, samples):
        app.include_router(module.router)
    return app


app = create_app()
