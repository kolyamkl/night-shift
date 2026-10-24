"""Question and answer turns of a document, encrypted, oldest first."""

from ..core.errors import MissingDocument
from ..db.database import Database
from .documents import iso


class ChatRepository:
    def __init__(self, db: Database):
        self._db = db

    def add_turn(self, doc_id: str, turn: dict, *, owner_id: str) -> tuple[int, str]:
        """Store one question and answer, encrypted; returns (turn_id, created_at)."""
        payload = self._db.envelope.seal(doc_id, "turn", turn)
        with self._db.connect() as conn:
            row = conn.execute("""WITH d AS (UPDATE veil_documents SET updated_at = now()
                    WHERE doc_id = %s AND owner_id = %s RETURNING doc_id, owner_id)
                INSERT INTO veil_chat_turns (doc_id, owner_id, payload) SELECT doc_id, owner_id, %s FROM d
                RETURNING turn_id, created_at""", (doc_id, owner_id, payload)).fetchone()
        if row is None:
            raise MissingDocument()
        return row[0], iso(row[1])

    def turns(self, doc_id: str, *, owner_id: str) -> list[dict]:
        """Chat turns of one document, oldest first."""
        with self._db.connect() as conn:
            rows = conn.execute("""SELECT t.turn_id, t.created_at, t.payload FROM veil_chat_turns t
                JOIN veil_documents d USING (doc_id) WHERE t.doc_id = %s AND d.owner_id = %s
                ORDER BY t.turn_id""", (doc_id, owner_id)).fetchall()
        return [{"turn_id": turn_id, "created_at": iso(created_at), **self._db.envelope.open(doc_id, "turn", payload)}
                for turn_id, created_at, payload in rows]
