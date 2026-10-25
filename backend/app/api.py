"""Route registry: every module's router, plus /api/health. Add a new module's router here (one line)."""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from app.dependencies import DatabaseDep, ModelsDep
from app.modules.ask.router import router as ask_router
from app.modules.auth.router import router as auth_router
from app.modules.corrections.router import router as corrections_router
from app.modules.documents.router import router as documents_router
from app.modules.files.router import router as files_router
from app.modules.samples.router import router as samples_router
from app.modules.scan.router import router as scan_router

system_router = APIRouter(prefix="/api")


class Health(BaseModel):
    model: Literal["on", "off"]
    t1_model: str | None
    t1_prompt: str
    t2_model: str | None
    key_source: str | None  # where the Mubit key came from; never the key
    database: str


@system_router.get("/health")
def health(db: DatabaseDep, models: ModelsDep) -> Health:
    """Which model calls are on, and that the database answers (503 when it does not)."""
    db.healthy()
    on = models.t1_on
    return Health(
        model="on" if on else "off",
        t1_model=models.t1_model if on else None,
        t1_prompt=models.t1_prompt,
        t2_model=models.t2_model if models.t2 else None,
        key_source=models.key_source if on else None,
        database="postgresql",
    )


ROUTERS = (
    auth_router,
    system_router,
    documents_router,
    scan_router,
    files_router,
    ask_router,
    corrections_router,
    samples_router,
)
