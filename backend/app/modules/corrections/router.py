"""/api/documents/{doc_id}/corrections: hide or unhide one value."""

from fastapi import APIRouter

from app.dependencies import ModelsDep
from app.modules.auth.dependencies import CurrentUser
from app.modules.corrections.schemas import Correction
from app.modules.corrections.service import CorrectionService
from app.modules.documents.dependencies import DocumentRepositoryDep
from app.modules.documents.schemas import ScanResult

router = APIRouter(prefix="/api/documents")


@router.post("/{doc_id}/corrections")
def correct(
    doc_id: str, body: Correction, user: CurrentUser, repo: DocumentRepositoryDep, models: ModelsDep
) -> ScanResult:
    return CorrectionService(repo).apply(doc_id, body, owner_id=user.id, model="on" if models.t1_on else "off")
