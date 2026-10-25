"""A reviewer's fixes: hide a value the scan missed, or show one it should not have hidden.

The fix is applied on top of the stored result with no new model call (pipeline.rebuild), and later
scans keep it, since the reviewer's decisions travel with the result.
"""

from app.core.errors import BadRequestError
from app.modules.corrections.schemas import Correction
from app.modules.documents.repository import DocumentRepository
from app.modules.documents.schemas import ModelState, ScanResult
from app.modules.documents.service import DocumentService
from app.redaction.pipeline import rebuild


class CorrectionService:
    def __init__(self, repo: DocumentRepository) -> None:
        self.repo = repo
        self.documents = DocumentService(repo)

    def apply(self, doc_id: str, body: Correction, *, owner_id: str, model: ModelState) -> ScanResult:
        saved = self.documents.get_scanned(doc_id, owner_id=owner_id)
        doc, res = saved.document, saved.result
        value = body.text.strip()
        if not value or value not in doc.text:
            raise BadRequestError("That text is not in the document.")
        if body.action == "hide":
            new = rebuild(doc, res, hide={value: body.type})
        elif body.action == "unhide":
            new = rebuild(doc, res, unhide={value})
        else:
            raise BadRequestError("action must be hide or unhide")
        self.repo.save_result(doc_id, new, saved.revision, owner_id=owner_id)
        return ScanResult.of(doc, new, model)
