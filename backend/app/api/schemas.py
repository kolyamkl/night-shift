"""Request bodies and the JSON shapes the frontend reads (frontend/src/api.ts)."""

import re
from dataclasses import asdict
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from ..domain.extract import Document
from ..domain.pipeline import PipelineResult
from ..llm.models import Models


class Credentials(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(min_length=8, max_length=128, repr=False)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value):
        value = value.strip().lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("Enter a valid email address.")
        return value


class StatusChange(BaseModel):
    status: Literal["review", "approved", "declined"]


class Ask(BaseModel):
    question: str


class Correction(BaseModel):
    action: str  # "hide" or "unhide"
    text: str
    type: str = "CUSTOM"


def document_out(doc: Document) -> dict:
    return {"doc_id": doc.doc_id, "kind": doc.kind, "filename": doc.filename, "text": doc.text,
            "pages": [{"width": w, "height": h} for w, h in doc.pages]}


def result_out(doc: Document, res: PipelineResult, models: Models) -> dict:
    return {
        "doc_id": doc.doc_id,
        "redacted_text": res.redacted_text,
        "entities": [{"start": s.start, "end": s.end, "text": s.text, "type": s.type,
                      "placeholder": res.vault.placeholder_for(s.text, s.type)} for s in res.spans],
        "boxes": [asdict(b) for b in res.boxes],
        "chunks": [asdict(c) for c in res.chunks],
        "stats": res.stats,
        "model": "on" if models.on else "off",
    }
