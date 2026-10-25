"""MuGuard API: upload or paste, redact through Mubit, download the redacted file, ask about it, fix it.

Run from backend/: uv run --env-file ../.env uvicorn app.main:app --reload --port 8000
Documents and redactions persist encrypted in PostgreSQL; document text is never logged.
docs/architecture.md describes the layers: core (plumbing), modules (HTTP features), and the domain
packages redaction, llm and ingest that the services call.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import psycopg
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import ROUTERS
from app.core.config import Settings
from app.core.db import Database
from app.core.errors import register_error_handlers
from app.core.logging import RequestIdMiddleware, configure_logging
from app.core.security import protect_browser_requests
from app.llm.models import build_models, describe

log = logging.getLogger("veil")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    db = Database.from_settings(app.state.settings)
    try:
        db.initialize()
    except psycopg.Error:
        raise RuntimeError("PostgreSQL is unavailable. Check DATABASE_URL and start the database.") from None
    app.state.db = db
    yield


def create_app(settings: Settings | None = None) -> FastAPI:
    configure_logging()
    settings = settings or Settings.load()
    app = FastAPI(title="MuGuard", lifespan=lifespan)
    app.state.settings = settings
    app.state.models = build_models(settings)
    log.info(describe(settings, settings.key_source))

    register_error_handlers(app)
    # Order matters: the last middleware added runs first. The request id wraps everything; the
    # request protection check runs before CORS, as it always has.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=True,
    )
    app.middleware("http")(protect_browser_requests)
    app.add_middleware(RequestIdMiddleware)
    for router in ROUTERS:
        app.include_router(router)
    return app


app = create_app()
