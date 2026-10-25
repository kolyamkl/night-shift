"""Document bodies the API sends and accepts. Field names and order are the frontend's contract
(frontend/src/api.ts): add optional fields only, never rename or remove one."""

from dataclasses import asdict
from typing import Literal

from pydantic import BaseModel

from app.redaction.document import Document
from app.redaction.pipeline import PipelineResult

ModelState = Literal["on", "off"]
ReviewStatus = Literal["review", "approved", "declined"]


class PageSize(BaseModel):
    width: float
    height: float


class DocumentOut(BaseModel):
    """A stored document: its text, and each page's size in PDF points (none for text)."""

    doc_id: str
    kind: str  # "text" or "pdf"
    filename: str
    text: str
    pages: list[PageSize]

    @classmethod
    def of(cls, doc: Document) -> "DocumentOut":
        return cls(
            doc_id=doc.doc_id,
            kind=doc.kind,
            filename=doc.filename,
            text=doc.text,
            pages=[PageSize(width=w, height=h) for w, h in doc.pages],
        )


class EntityOut(BaseModel):
    start: int
    end: int
    text: str
    type: str
    placeholder: str


class BoxOut(BaseModel):
    """One black box on a PDF page, in PDF points."""

    page: int
    x0: float
    y0: float
    x1: float
    y1: float
    type: str
    placeholder: str
    span_index: int


class ChunkOut(BaseModel):
    index: int
    chunk_id: str
    start: int
    end: int
    status: str  # "ok", "error", "empty" (whitespace only, no call) or "off" (no model, no call)
    error: str | None
    mreq_id: str | None
    latency_ms: int | None
    found: int


class ScanResult(BaseModel):
    """The redaction of one document: what goes to the AI provider, and where each value was."""

    doc_id: str
    redacted_text: str
    entities: list[EntityOut]
    boxes: list[BoxOut]
    chunks: list[ChunkOut]
    stats: dict[str, int]
    model: ModelState

    @classmethod
    def of(cls, doc: Document, res: PipelineResult, model: ModelState) -> "ScanResult":
        return cls(
            doc_id=doc.doc_id,
            redacted_text=res.redacted_text,
            entities=[
                EntityOut(
                    start=s.start,
                    end=s.end,
                    text=s.text,
                    type=s.type,
                    placeholder=res.vault.placeholder_for(s.text, s.type),
                )
                for s in res.spans
            ],
            boxes=[BoxOut(**asdict(b)) for b in res.boxes],
            chunks=[ChunkOut(**asdict(c)) for c in res.chunks],
            stats=res.stats,
            model=model,
        )


class Turn(BaseModel):
    """One question and answer about a document, oldest first."""

    turn_id: int
    created_at: str  # ISO 8601 UTC, as JavaScript's Date.toISOString gives
    question: str
    sent_question: str  # the question as the AI provider saw it, pseudonymised
    answer: str
    answer_with_placeholders: str
    unknown_placeholders: list[str]
    mreq_id: str | None


class StoredDocument(BaseModel):
    document: DocumentOut
    revision: int
    result: ScanResult | None
    status: str  # new, review, approved or declined
    turns: list[Turn]


class DocumentSummary(BaseModel):
    """One row of the document list: no document text."""

    doc_id: str
    filename: str
    kind: str
    pages: int
    status: str
    created_at: str
    updated_at: str
    has_result: bool
    changes: int | None
    turns: int


class StatusChange(BaseModel):
    status: ReviewStatus


class StatusOut(BaseModel):
    doc_id: str
    status: str
