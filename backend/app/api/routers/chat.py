"""/api/documents/{id}/ask: a question about the redacted document."""

from fastapi import APIRouter

from ..deps import Chat, User
from ..schemas import Ask

router = APIRouter(prefix="/api/documents/{doc_id}", tags=["chat"])


@router.post("/ask")
def ask(doc_id: str, body: Ask, user: User, chat: Chat) -> dict:
    return chat.ask(doc_id, body.question, user["id"])
