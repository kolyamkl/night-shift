"""/api/documents: add, list, open, review status, delete, page images and the redacted file."""

from urllib.parse import quote

from fastapi import APIRouter, File, Form, Query, UploadFile
from fastapi.responses import Response

from ...core.errors import TooLarge
from ..deps import ConfigDep, Documents, ModelsDep, User
from ..schemas import StatusChange, document_out, result_out

router = APIRouter(prefix="/api/documents", tags=["documents"])
READ_BLOCK = 1024 * 1024


@router.get("")
def list_documents(user: User, documents: Documents) -> list[dict]:
    return documents.summaries(user["id"])


@router.post("")
async def create_document(user: User, documents: Documents, config: ConfigDep, text: str | None = Form(None),
                          file: UploadFile | None = File(None)) -> dict:
    if file is None:
        return document_out(documents.add_paste(text, user["id"]))
    data = await _read_limited(file, config.max_upload)
    return document_out(documents.add_upload(data, file.filename or "upload", user["id"]))


async def _read_limited(file: UploadFile, limit: int) -> bytes:
    """The upload, refusing it as soon as it passes the limit rather than after reading all of it."""
    parts, size = [], 0
    while block := await file.read(READ_BLOCK):
        size += len(block)
        if size > limit:
            raise TooLarge(f"The file is larger than {limit // (1024 * 1024)} MB.")
        parts.append(block)
    return b"".join(parts)


@router.get("/{doc_id}")
def read_document(doc_id: str, user: User, documents: Documents, models: ModelsDep) -> dict:
    saved = documents.get(doc_id, user["id"])
    return {"document": document_out(saved.document), "revision": saved.revision,
            "result": result_out(saved.document, saved.result, models) if saved.result else None,
            "status": saved.status, "turns": documents.turns(doc_id, user["id"])}


@router.patch("/{doc_id}")
def change_status(doc_id: str, body: StatusChange, user: User, documents: Documents) -> dict:
    return {"doc_id": doc_id, "status": documents.set_status(doc_id, body.status, user["id"])}


@router.delete("/{doc_id}", status_code=204)
def delete_document(doc_id: str, user: User, documents: Documents) -> Response:
    documents.delete(doc_id, user["id"])
    return Response(status_code=204)


@router.get("/{doc_id}/pages/{page}.png")
def page_image(doc_id: str, page: int, user: User, documents: Documents,
               scale: float = Query(1.5, gt=0, le=4)) -> Response:
    return Response(documents.page_image(doc_id, page, scale, user["id"]), media_type="image/png")


@router.get("/{doc_id}/file")
def redacted_file(doc_id: str, user: User, documents: Documents) -> Response:
    out = documents.redacted_file(doc_id, user["id"])
    return Response(out.content, media_type=out.media_type, headers={"Content-Disposition": attachment(out.filename)})


def attachment(filename: str) -> str:
    """A Content-Disposition any browser reads, for any file name: an ASCII fallback and the UTF-8 name."""
    fallback = "".join(c if 32 <= ord(c) < 127 and c not in '"\\' else "_" for c in filename)
    return f"attachment; filename=\"{fallback}\"; filename*=UTF-8''{quote(filename)}"
