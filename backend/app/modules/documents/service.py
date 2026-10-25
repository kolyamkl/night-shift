"""Documents: create from an upload, list, open, change the review status, delete.

Other modules (scan, corrections, ask, files) work on a stored document through this service and
its repository, always scoped to the signed-in owner.
"""

from dataclasses import dataclass

from app.core.errors import ConflictError
from app.modules.documents.repository import DocumentRepository
from app.modules.documents.schemas import (
    DocumentOut,
    DocumentSummary,
    ModelState,
    ReviewStatus,
    ScanResult,
    StatusOut,
    StoredDocument,
    Turn,
)
from app.redaction.document import Document
from app.redaction.pipeline import PipelineResult


@dataclass(frozen=True)
class Scanned:
    """A document that has a result, at the revision it was read."""

    document: Document
    result: PipelineResult
    revision: int


class DocumentService:
    def __init__(self, repo: DocumentRepository) -> None:
        self.repo = repo

    def create(self, doc: Document, *, owner_id: str) -> DocumentOut:
        self.repo.create(doc, owner_id=owner_id)
        return DocumentOut.of(doc)

    def list(self, *, owner_id: str) -> list[DocumentSummary]:
        """The owner's documents, last updated first, at most 200; summaries only, no document text."""
        return [DocumentSummary(**row) for row in self.repo.list_documents(owner_id=owner_id)]

    def read(self, doc_id: str, *, owner_id: str, model: ModelState) -> StoredDocument:
        saved = self.repo.get(doc_id, owner_id=owner_id)
        return StoredDocument(
            document=DocumentOut.of(saved.document),
            revision=saved.revision,
            result=ScanResult.of(saved.document, saved.result, model) if saved.result else None,
            status=saved.status,
            turns=[Turn(**turn) for turn in self.repo.turns(doc_id, owner_id=owner_id)],
        )

    def set_status(self, doc_id: str, status: ReviewStatus, *, owner_id: str) -> StatusOut:
        return StatusOut(doc_id=doc_id, status=self.repo.set_status(doc_id, status, owner_id=owner_id))

    def delete(self, doc_id: str, *, owner_id: str) -> None:
        """Deletes the result and the chat turns too."""
        self.repo.delete(doc_id, owner_id=owner_id)

    def get(self, doc_id: str, *, owner_id: str) -> Document:
        return self.repo.get(doc_id, owner_id=owner_id).document

    def get_scanned(self, doc_id: str, *, owner_id: str) -> Scanned:
        """The document with its newest result; 409 if it was never scanned."""
        saved = self.repo.get(doc_id, owner_id=owner_id)
        if saved.result is None:
            raise ConflictError("Scan the document first.")
        return Scanned(saved.document, saved.result, saved.revision)
