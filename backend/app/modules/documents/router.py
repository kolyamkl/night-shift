"""/api/documents: upload or paste, list, open, change the review status, delete."""

from typing import Annotated

from fastapi import APIRouter, File, Form, Response, UploadFile

from app.dependencies import ModelsDep
from app.modules.auth.dependencies import CurrentUser
from app.modules.documents import uploads
from app.modules.documents.dependencies import DocumentServiceDep
from app.modules.documents.schemas import DocumentOut, DocumentSummary, StatusChange, StatusOut, StoredDocument

router = APIRouter(prefix="/api/documents")


@router.get("")
def list_documents(user: CurrentUser, documents: DocumentServiceDep) -> list[DocumentSummary]:
    """The caller's documents, last updated first, at most 200; summaries only, no document text."""
    return documents.list(owner_id=user.id)


@router.get("/{doc_id}")
def read_document(doc_id: str, user: CurrentUser, documents: DocumentServiceDep, models: ModelsDep) -> StoredDocument:
    return documents.read(doc_id, owner_id=user.id, model="on" if models.t1_on else "off")


@router.patch("/{doc_id}")
def change_status(doc_id: str, body: StatusChange, user: CurrentUser, documents: DocumentServiceDep) -> StatusOut:
    return documents.set_status(doc_id, body.status, owner_id=user.id)


@router.delete("/{doc_id}", status_code=204)
def delete_document(doc_id: str, user: CurrentUser, documents: DocumentServiceDep) -> Response:
    documents.delete(doc_id, owner_id=user.id)
    return Response(status_code=204)


@router.post("")
def create_document(
    user: CurrentUser,
    documents: DocumentServiceDep,
    text: Annotated[str | None, Form()] = None,
    file: Annotated[UploadFile | None, File()] = None,
) -> DocumentOut:
    # A plain def runs in the threadpool: PDF parsing, OCR and the database write would otherwise
    # block the event loop, and with it every other request and scan stream.
    doc = uploads.from_pasted(text) if file is None else uploads.from_file(file.file.read(), file.filename)
    return documents.create(doc, owner_id=user.id)
