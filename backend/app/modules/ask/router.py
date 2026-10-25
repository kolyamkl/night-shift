"""/api/documents/{doc_id}/ask: a question about the redacted document."""

from fastapi import APIRouter

from app.dependencies import ModelsDep
from app.modules.ask.schemas import Answer, Ask
from app.modules.ask.service import AskService
from app.modules.auth.dependencies import CurrentUser
from app.modules.documents.dependencies import DocumentRepositoryDep

router = APIRouter(prefix="/api/documents")


@router.post("/{doc_id}/ask")
def ask(doc_id: str, body: Ask, user: CurrentUser, repo: DocumentRepositoryDep, models: ModelsDep) -> Answer:
    return AskService(repo, models.t2).ask(doc_id, body.question, owner_id=user.id)
