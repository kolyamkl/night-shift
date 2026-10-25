"""Ask a question about a scanned document its owner approved. The model (T2) sees only the redacted
text and the question pseudonymised with the document's vault (redaction.question); its answer is
restored with that vault and stored, encrypted, as a chat turn. A failed call stores nothing."""

from app.core.errors import BadGatewayError, ServiceUnavailableError
from app.llm.t2 import T2
from app.modules.ask.schemas import Answer
from app.modules.documents.repository import DocumentRepository
from app.modules.documents.service import DocumentService
from app.redaction.question import plain, pseudonymise
from app.redaction.vault import restore


class AskService:
    def __init__(self, repo: DocumentRepository, t2: T2 | None) -> None:
        self.repo = repo
        self.documents = DocumentService(repo)
        self.t2 = t2

    def ask(self, doc_id: str, question: str, *, owner_id: str) -> Answer:
        res = self.documents.get_approved(doc_id, owner_id=owner_id).result
        if not self.t2:
            raise ServiceUnavailableError("The chat model is off. Start the backend with MUBIT_API_KEY set.")
        sent_question, vault = pseudonymise(question, res.vault)  # the question is pseudonymised too
        try:
            raw, mreq = self.t2(sent_question, res.redacted_text)
        except Exception as exc:  # noqa: BLE001 - any provider failure is a bad gateway for the client
            raise BadGatewayError(f"The model did not answer: {exc}") from None
        raw = plain(raw)
        answer, unknown = restore(raw, vault)
        turn = {
            "question": question,
            "sent_question": sent_question,
            "answer": answer,
            "answer_with_placeholders": raw,
            "unknown_placeholders": unknown,
            "mreq_id": mreq,
        }
        turn_id, created_at = self.repo.add_turn(doc_id, turn, owner_id=owner_id)
        return Answer(
            answer=answer,
            answer_with_placeholders=raw,
            sent_text=res.redacted_text,
            sent_question=sent_question,
            unknown_placeholders=unknown,
            mreq_id=mreq,
            turn_id=turn_id,
            created_at=created_at,
        )
