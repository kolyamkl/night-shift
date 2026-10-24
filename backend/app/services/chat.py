"""Questions about a document. The AI sees only the redacted text and a pseudonymised question; the
real values are put back into its answer here, on the server."""

from evalkit.redact import restore

from ..core.errors import ModelFailed, Unavailable
from ..core.log import log
from ..domain.question import plain, pseudonymise
from ..llm.models import Models
from ..repositories import Storage
from .documents import DocumentService


class ChatService:
    def __init__(self, storage: Storage, models: Models):
        self._documents = DocumentService(storage)
        self._chat = storage.chat
        self._models = models

    def ask(self, doc_id: str, question: str, owner_id: str) -> dict:
        res = self._documents.scanned(doc_id, owner_id).result
        t2 = self._models.t2
        if not t2:
            raise Unavailable("The chat model is off. Start the backend with MUBIT_API_KEY set.")
        sent_question, vault = pseudonymise(question, res.vault)
        try:
            raw, mreq = t2(sent_question, res.redacted_text)
        except Exception as exc:  # noqa: BLE001 - the provider's message may echo the request, so it is not shown
            log.error("answer failed doc=%s error=%s", doc_id, type(exc).__name__)
            raise ModelFailed() from None
        raw = plain(raw)
        answer, unknown = restore(raw, vault)
        turn = {"question": question, "sent_question": sent_question, "answer": answer,
                "answer_with_placeholders": raw, "unknown_placeholders": unknown, "mreq_id": mreq}
        turn_id, created_at = self._chat.add_turn(doc_id, turn, owner_id=owner_id)
        return {"answer": answer, "answer_with_placeholders": raw, "sent_text": res.redacted_text,
                "sent_question": sent_question, "unknown_placeholders": unknown, "mreq_id": mreq,
                "turn_id": turn_id, "created_at": created_at}
