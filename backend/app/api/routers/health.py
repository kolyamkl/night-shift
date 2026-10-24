"""/api/health: whether the database answers and which models are on (never the key)."""

from typing import Annotated

from fastapi import APIRouter, Depends

from ...repositories import Storage
from ..deps import ModelsDep, get_storage

router = APIRouter(tags=["health"])


@router.get("/api/health")
def health(storage: Annotated[Storage, Depends(get_storage)], models: ModelsDep) -> dict:
    storage.db.healthy()
    return {**models.health(), "database": "postgresql"}
