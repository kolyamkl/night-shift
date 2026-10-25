"""Documents, their scan results, review status and chat turns in PostgreSQL.

Everything that names a person is encrypted (core.crypto): the document with its text and source
file, the redaction result with its vault, the list summary with the file name, and each chat turn.
Every query is scoped by owner, so another user's document is simply not found. No pickle, no
plaintext vaults, no in-memory fallback.
"""

import base64
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

from app.core.db import Database
from app.core.errors import ConflictError, NotFoundError
from app.redaction.document import Document, Word
from app.redaction.pipeline import Box, ChunkInfo, PipelineResult
from app.redaction.spans import Span
from app.redaction.vault import Vault

LIST_LIMIT = 200


class DocumentNotFound(NotFoundError):
    default_detail = "Document not found."


class StaleRevision(ConflictError):
    """A newer scan or correction was saved since this one read the document."""

    default_detail = "The document changed. Reload it before trying again."


@dataclass
class Snapshot:
    document: Document
    result: PipelineResult | None
    revision: int
    status: str = "new"  # new, review, approved or declined


def iso(moment: datetime) -> str:
    """UTC in the form JavaScript's Date.toISOString gives."""
    return moment.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class DocumentRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def _encrypt(self, doc_id: str, kind: str, data: Any) -> bytes:
        return self.db.cipher.seal(doc_id, kind, data)

    def _decrypt(self, doc_id: str, kind: str, payload: bytes | memoryview) -> Any:
        return self.db.cipher.open(doc_id, kind, payload)

    def create(self, doc: Document, *, owner_id: str) -> None:
        data = asdict(doc)
        data["source"] = base64.b64encode(doc.source).decode() if doc.source is not None else None
        meta = {"filename": doc.filename, "kind": doc.kind, "pages": len(doc.pages), "changes": None}
        with self.db.connect() as conn:
            conn.execute(
                "INSERT INTO veil_documents (doc_id, payload, owner_id, meta) VALUES (%s, %s, %s, %s)",
                (
                    doc.doc_id,
                    self._encrypt(doc.doc_id, "document", data),
                    owner_id,
                    self._encrypt(doc.doc_id, "meta", meta),
                ),
            )

    def get(self, doc_id: str, *, owner_id: str) -> Snapshot:
        with self.db.connect() as conn:
            row = conn.execute(
                """SELECT d.payload, r.payload, d.revision, d.status FROM veil_documents d
                LEFT JOIN veil_redactions r USING (doc_id) WHERE d.doc_id = %s AND d.owner_id = %s""",
                (doc_id, owner_id),
            ).fetchone()
        return self._snapshot(doc_id, row)

    def begin_scan(self, doc_id: str, *, owner_id: str) -> Snapshot:
        """Reserve the newest scan atomically, including across backend workers."""
        with self.db.connect() as conn:
            row = conn.execute(
                """UPDATE veil_documents d SET revision = revision + 1, updated_at = now()
                WHERE doc_id = %s AND owner_id = %s
                RETURNING d.payload, (SELECT payload FROM veil_redactions WHERE doc_id = d.doc_id), d.revision,
                d.status""",
                (doc_id, owner_id),
            ).fetchone()
        return self._snapshot(doc_id, row)

    def is_current(self, doc_id: str, revision: int, *, owner_id: str) -> bool:
        with self.db.connect() as conn:
            return (
                conn.execute(
                    "SELECT 1 FROM veil_documents WHERE doc_id = %s AND revision = %s AND owner_id = %s",
                    (doc_id, revision, owner_id),
                ).fetchone()
                is not None
            )

    def _snapshot(self, doc_id: str, row: tuple[Any, ...] | None) -> Snapshot:
        if row is None:
            raise DocumentNotFound
        data = self._decrypt(doc_id, "document", row[0])
        data["words"] = [Word(**{**w, "bbox": tuple(w["bbox"]), "line": tuple(w["line"])}) for w in data["words"]]
        data["pages"] = [tuple(p) for p in data["pages"]]
        data["source"] = base64.b64decode(data["source"]) if data["source"] is not None else None
        doc = Document(**data)
        result = None
        if row[1] is not None:
            raw = self._decrypt(doc_id, "result", row[1])
            result = PipelineResult(
                spans=[Span(**s) for s in raw["spans"]],
                redacted_text=raw["redacted_text"],
                vault=Vault(**raw["vault"]),
                boxes=[Box(**b) for b in raw["boxes"]],
                chunks=[self._chunk(c, i) for i, c in enumerate(raw["chunks"])],
                stats=raw["stats"],
                model_values=raw["model_values"],
                hidden=raw["hidden"],
                unhidden=set(raw["unhidden"]),
                chunk_values=raw.get("chunk_values", []),
                plan=raw.get("plan", ""),
            )
        return Snapshot(doc, result, row[2], row[3])

    @staticmethod
    def _chunk(data: dict[str, Any], index: int) -> ChunkInfo:
        # Snapshots saved before live scanning lack index/status/latency.
        legacy_status = (
            "off"
            if data.get("error") == "model off"
            else "error"
            if data.get("error")
            else "ok"
            if data.get("mreq_id") or data.get("found")
            else "empty"
        )
        return ChunkInfo(**{"index": index, "status": legacy_status, **data})

    def save_result(self, doc_id: str, result: PipelineResult, expected_revision: int, *, owner_id: str) -> int:
        data = asdict(result)
        data["unhidden"] = sorted(result.unhidden)
        payload = self._encrypt(doc_id, "result", data)
        with self.db.connect() as conn:
            # A first result opens review; approved and declined stay, since editing after approval is allowed.
            row = conn.execute(
                """UPDATE veil_documents SET revision = revision + 1, updated_at = now(),
                status = CASE WHEN status = 'new' THEN 'review' ELSE status END
                WHERE doc_id = %s AND revision = %s AND owner_id = %s RETURNING revision, meta""",
                (doc_id, expected_revision, owner_id),
            ).fetchone()
            if row is None:
                if not conn.execute(
                    "SELECT 1 FROM veil_documents WHERE doc_id = %s AND owner_id = %s", (doc_id, owner_id)
                ).fetchone():
                    raise DocumentNotFound
                raise StaleRevision
            conn.execute(
                """INSERT INTO veil_redactions (doc_id, payload) VALUES (%s, %s)
                ON CONFLICT (doc_id) DO UPDATE SET payload = EXCLUDED.payload""",
                (doc_id, payload),
            )
            if row[1] is not None:  # a row from before migration 003 gets its summary when first listed
                meta = {**self._decrypt(doc_id, "meta", row[1]), "changes": len(result.spans)}
                conn.execute(
                    "UPDATE veil_documents SET meta = %s WHERE doc_id = %s",
                    (self._encrypt(doc_id, "meta", meta), doc_id),
                )
            return row[0]

    def list_documents(self, *, owner_id: str, limit: int = LIST_LIMIT) -> list[dict[str, Any]]:
        """The owner's documents, last updated first, read from the small encrypted summaries."""
        with self.db.connect() as conn:
            rows = conn.execute(
                """SELECT d.doc_id, d.status, d.created_at, d.updated_at, d.meta,
                    r.doc_id IS NOT NULL, (SELECT count(*) FROM veil_chat_turns t WHERE t.doc_id = d.doc_id)
                FROM veil_documents d LEFT JOIN veil_redactions r USING (doc_id)
                WHERE d.owner_id = %s ORDER BY d.updated_at DESC, d.doc_id LIMIT %s""",
                (owner_id, limit),
            ).fetchall()
        legacy = self._fill_meta([r[0] for r in rows if r[4] is None], owner_id)
        out: list[dict[str, Any]] = []
        for doc_id, stored_status, created_at, updated_at, meta, has_result, turns in rows:
            status = stored_status
            if meta is not None:
                summary = self._decrypt(doc_id, "meta", meta)
            elif doc_id in legacy:
                summary, status = legacy[doc_id]
            else:  # deleted while listing
                continue
            out.append(
                {
                    "doc_id": doc_id,
                    "filename": summary["filename"],
                    "kind": summary["kind"],
                    "pages": summary["pages"],
                    "status": status,
                    "created_at": iso(created_at),
                    "updated_at": iso(updated_at),
                    "has_result": has_result,
                    "changes": summary["changes"] if has_result else None,
                    "turns": turns,
                }
            )
        return out

    def _fill_meta(self, doc_ids: list[str], owner_id: str) -> dict[str, tuple[dict[str, Any], str]]:
        """(summary, status) for rows saved before migration 003, or by the previous release while a
        deploy overlapped it: read once from the full payloads, then stored."""
        if not doc_ids:
            return {}
        filled: dict[str, tuple[dict[str, Any], str]] = {}
        with self.db.connect() as conn:
            rows = conn.execute(
                """SELECT d.doc_id, d.payload, r.payload, d.revision, d.status
                FROM veil_documents d LEFT JOIN veil_redactions r USING (doc_id)
                WHERE d.doc_id = ANY(%s) AND d.owner_id = %s""",
                (doc_ids, owner_id),
            ).fetchall()
            for doc_id, document, result, revision, stored_status in rows:
                data = self._decrypt(doc_id, "document", document)
                spans = self._decrypt(doc_id, "result", result)["spans"] if result is not None else None
                summary = {
                    "filename": data["filename"],
                    "kind": data["kind"],
                    "pages": len(data["pages"]),
                    "changes": len(spans) if spans is not None else None,
                }
                # A document scanned by a release without review status opens in review.
                status = "review" if stored_status == "new" and result is not None else stored_status
                # Skipped if a result was saved meanwhile; the next listing reads that one.
                conn.execute(
                    """UPDATE veil_documents SET meta = %s, status = %s
                    WHERE doc_id = %s AND revision = %s AND meta IS NULL""",
                    (self._encrypt(doc_id, "meta", summary), status, doc_id, revision),
                )
                filled[doc_id] = summary, status
        return filled

    def set_status(self, doc_id: str, status: str, *, owner_id: str) -> str:
        with self.db.connect() as conn:
            row = conn.execute(
                """UPDATE veil_documents SET status = %s,
                updated_at = CASE WHEN status = %s THEN updated_at ELSE now() END
                WHERE doc_id = %s AND owner_id = %s RETURNING status""",
                (status, status, doc_id, owner_id),
            ).fetchone()
        if row is None:
            raise DocumentNotFound
        return row[0]

    def add_turn(self, doc_id: str, turn: dict[str, Any], *, owner_id: str) -> tuple[int, str]:
        """Store one question and answer, encrypted; returns (turn_id, created_at)."""
        payload = self._encrypt(doc_id, "turn", turn)
        with self.db.connect() as conn:
            row = conn.execute(
                """WITH d AS (UPDATE veil_documents SET updated_at = now()
                    WHERE doc_id = %s AND owner_id = %s RETURNING doc_id, owner_id)
                INSERT INTO veil_chat_turns (doc_id, owner_id, payload) SELECT doc_id, owner_id, %s FROM d
                RETURNING turn_id, created_at""",
                (doc_id, owner_id, payload),
            ).fetchone()
        if row is None:
            raise DocumentNotFound
        return row[0], iso(row[1])

    def turns(self, doc_id: str, *, owner_id: str) -> list[dict[str, Any]]:
        """Chat turns of one document, oldest first."""
        with self.db.connect() as conn:
            rows = conn.execute(
                """SELECT t.turn_id, t.created_at, t.payload FROM veil_chat_turns t
                JOIN veil_documents d USING (doc_id) WHERE t.doc_id = %s AND d.owner_id = %s
                ORDER BY t.turn_id""",
                (doc_id, owner_id),
            ).fetchall()
        return [
            {"turn_id": turn_id, "created_at": iso(created_at), **self._decrypt(doc_id, "turn", payload)}
            for turn_id, created_at, payload in rows
        ]

    def delete(self, doc_id: str, *, owner_id: str) -> None:
        """Deletes the result and chat turns too (ON DELETE CASCADE)."""
        with self.db.connect() as conn:
            row = conn.execute(
                "DELETE FROM veil_documents WHERE doc_id = %s AND owner_id = %s RETURNING doc_id", (doc_id, owner_id)
            ).fetchone()
            if row is None:
                raise DocumentNotFound
