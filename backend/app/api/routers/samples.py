"""/api/samples: the invented sample documents, their thumbnails, and opening one as your own copy."""

from fastapi import APIRouter, Query
from fastapi.responses import Response

from ..deps import Documents, Samples, User
from ..schemas import document_out

router = APIRouter(prefix="/api/samples", tags=["samples"])


@router.get("")
def samples(library: Samples) -> list[dict]:
    return library.cards()


@router.get("/{name}/thumb.png")
def sample_thumb(name: str, library: Samples, width: int = Query(120, ge=16, le=600)) -> Response:
    return Response(library.thumbnail(name, width), media_type="image/png", headers={"Cache-Control": "max-age=3600"})


@router.post("/{name}")
def open_sample(name: str, user: User, library: Samples, documents: Documents) -> dict:
    return document_out(documents.add(library.document(name), user["id"]))
