"""Documents, their latest redaction result and review status. Every payload is encrypted (db.crypto);
only ids, owners, revisions, status and timestamps are stored in the clear."""

from dataclasses import dataclass
from datetime import datetime, timezone

from ..core.errors import MissingDocument, StaleRevision
from ..db.database import Database
from ..domain.extract import Document
from ..domain.pipeline import PipelineResult
from .codec import document_from_dict, document_to_dict, result_from_dict, result_to_dict


@dataclass
class Snapshot:
    document: Document
    result: PipelineResult | None
    revision: int
    status: str = "new"  # new, review, approved or declined


def iso(moment: datetime) -> str:
    """UTC in the form JavaScript's Date.toISOString gives."""
    return moment.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class DocumentRepository:
    def __init__(self, db: Database):
        self._db = db

    def _seal(self, doc_id: str, kind: str, data: dict) -> bytes:
        return self._db.envelope.seal(doc_id, kind, data)

    def _open(self, doc_id: str, kind: str, payload: bytes) -> dict:
        return self._db.envelope.open(doc_id, kind, payload)

    def create(self, doc: Document, *, owner_id: str):
        data = document_to_dict(doc)
        meta = {"filename": doc.filename, "kind": doc.kind, "pages": len(doc.pages), "changes": None}
        with self._db.connect() as conn:
            conn.execute("INSERT INTO veil_documents (doc_id, payload, owner_id, meta) VALUES (%s, %s, %s, %s)",
                         (doc.doc_id, self._seal(doc.doc_id, "document", data), owner_id,
                          self._seal(doc.doc_id, "meta", meta)))

    def get(self, doc_id: str, *, owner_id: str) -> Snapshot:
        with self._db.connect() as conn:
            row = conn.execute("""SELECT d.payload, r.payload, d.revision, d.status FROM veil_documents d
                LEFT JOIN veil_redactions r USING (doc_id) WHERE d.doc_id = %s AND d.owner_id = %s""",
                               (doc_id, owner_id)).fetchone()
        return self._snapshot(doc_id, row)

    def begin_scan(self, doc_id: str, *, owner_id: str) -> Snapshot:
        """Reserve the newest scan atomically, including across backend workers."""
        with self._db.connect() as conn:
            row = conn.execute("""UPDATE veil_documents d SET revision = revision + 1, updated_at = now()
                WHERE doc_id = %s AND owner_id = %s
                RETURNING d.payload, (SELECT payload FROM veil_redactions WHERE doc_id = d.doc_id), d.revision,
                d.status""",
                               (doc_id, owner_id)).fetchone()
        return self._snapshot(doc_id, row)

    def is_current(self, doc_id: str, revision: int, *, owner_id: str) -> bool:
        with self._db.connect() as conn:
            return conn.execute("SELECT 1 FROM veil_documents WHERE doc_id = %s AND revision = %s AND owner_id = %s",
                                (doc_id, revision, owner_id)).fetchone() is not None

    def _snapshot(self, doc_id: str, row) -> Snapshot:
        if row is None:
            raise MissingDocument()
        doc = document_from_dict(self._open(doc_id, "document", row[0]))
        result = result_from_dict(self._open(doc_id, "result", row[1])) if row[1] is not None else None
        return Snapshot(doc, result, row[2], row[3])

    def save_result(self, doc_id: str, result: PipelineResult, expected_revision: int, *, owner_id: str) -> int:
        payload = self._seal(doc_id, "result", result_to_dict(result))
        with self._db.connect() as conn:
            # A first result opens review; approved and declined stay, since editing after approval is allowed.
            row = conn.execute("""UPDATE veil_documents SET revision = revision + 1, updated_at = now(),
                status = CASE WHEN status = 'new' THEN 'review' ELSE status END
                WHERE doc_id = %s AND revision = %s AND owner_id = %s RETURNING revision, meta""",
                               (doc_id, expected_revision, owner_id)).fetchone()
            if row is None:
                if not conn.execute("SELECT 1 FROM veil_documents WHERE doc_id = %s AND owner_id = %s",
                                    (doc_id, owner_id)).fetchone():
                    raise MissingDocument()
                raise StaleRevision()
            conn.execute("""INSERT INTO veil_redactions (doc_id, payload) VALUES (%s, %s)
                ON CONFLICT (doc_id) DO UPDATE SET payload = EXCLUDED.payload""", (doc_id, payload))
            if row[1] is not None:  # a row from before migration 003 gets its summary when first listed
                meta = {**self._open(doc_id, "meta", row[1]), "changes": len(result.spans)}
                conn.execute("UPDATE veil_documents SET meta = %s WHERE doc_id = %s",
                             (self._seal(doc_id, "meta", meta), doc_id))
            return row[0]

    def list_documents(self, *, owner_id: str, limit: int = 200) -> list[dict]:
        """The owner's documents, last updated first, read from the small encrypted summaries."""
        with self._db.connect() as conn:
            rows = conn.execute("""SELECT d.doc_id, d.status, d.created_at, d.updated_at, d.meta,
                    r.doc_id IS NOT NULL, (SELECT count(*) FROM veil_chat_turns t WHERE t.doc_id = d.doc_id)
                FROM veil_documents d LEFT JOIN veil_redactions r USING (doc_id)
                WHERE d.owner_id = %s ORDER BY d.updated_at DESC, d.doc_id LIMIT %s""",
                                (owner_id, limit)).fetchall()
        legacy = self._fill_meta([r[0] for r in rows if r[4] is None], owner_id)
        out = []
        for doc_id, status, created_at, updated_at, meta, has_result, turns in rows:
            if meta is not None:
                summary = self._open(doc_id, "meta", meta)
            elif doc_id in legacy:
                summary, status = legacy[doc_id]
            else:  # deleted while listing
                continue
            out.append({"doc_id": doc_id, "filename": summary["filename"], "kind": summary["kind"],
                        "pages": summary["pages"], "status": status, "created_at": iso(created_at),
                        "updated_at": iso(updated_at), "has_result": has_result,
                        "changes": summary["changes"] if has_result else None, "turns": turns})
        return out

    def _fill_meta(self, doc_ids: list[str], owner_id: str) -> dict[str, tuple[dict, str]]:
        """(summary, status) for rows saved before migration 003, or by the previous release while a
        deploy overlapped it: read once from the full payloads, then stored."""
        if not doc_ids:
            return {}
        filled = {}
        with self._db.connect() as conn:
            rows = conn.execute("""SELECT d.doc_id, d.payload, r.payload, d.revision, d.status
                FROM veil_documents d LEFT JOIN veil_redactions r USING (doc_id)
                WHERE d.doc_id = ANY(%s) AND d.owner_id = %s""", (doc_ids, owner_id)).fetchall()
            for doc_id, document, result, revision, status in rows:
                data = self._open(doc_id, "document", document)
                spans = self._open(doc_id, "result", result)["spans"] if result is not None else None
                summary = {"filename": data["filename"], "kind": data["kind"], "pages": len(data["pages"]),
                           "changes": len(spans) if spans is not None else None}
                if status == "new" and result is not None:  # scanned by a release without review status
                    status = "review"
                # Skipped if a result was saved meanwhile; the next listing reads that one.
                conn.execute("""UPDATE veil_documents SET meta = %s, status = %s
                    WHERE doc_id = %s AND revision = %s AND meta IS NULL""",
                             (self._seal(doc_id, "meta", summary), status, doc_id, revision))
                filled[doc_id] = summary, status
        return filled

    def set_status(self, doc_id: str, status: str, *, owner_id: str) -> str:
        with self._db.connect() as conn:
            row = conn.execute("""UPDATE veil_documents SET status = %s,
                updated_at = CASE WHEN status = %s THEN updated_at ELSE now() END
                WHERE doc_id = %s AND owner_id = %s RETURNING status""",
                               (status, status, doc_id, owner_id)).fetchone()
        if row is None:
            raise MissingDocument()
        return row[0]

    def delete(self, doc_id: str, *, owner_id: str):
        """Deletes the result and chat turns too (ON DELETE CASCADE)."""
        with self._db.connect() as conn:
            row = conn.execute("DELETE FROM veil_documents WHERE doc_id = %s AND owner_id = %s RETURNING doc_id",
                               (doc_id, owner_id)).fetchone()
            if row is None:
                raise MissingDocument()
