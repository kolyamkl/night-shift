"""Corrections during review: hide a value the scan missed, or show one it should not have hidden.
The result is rebuilt from the saved scan, with no model call."""

from typing import Literal

from ..core.errors import BadRequest
from ..domain.extract import Document
from ..domain.pipeline import PipelineResult, rebuild
from ..repositories import Storage
from .documents import DocumentService


class ReviewService:
    def __init__(self, storage: Storage):
        self._documents = DocumentService(storage)
        self._docs = storage.documents

    def correct(self, doc_id: str, action: Literal["hide", "unhide"] | str, text: str, etype: str,
                owner_id: str) -> tuple[Document, PipelineResult]:
        saved = self._documents.scanned(doc_id, owner_id)
        doc, res = saved.document, saved.result
        value = text.strip()
        if not value or value not in doc.text:
            raise BadRequest("That text is not in the document.")
        if action == "hide":
            new = rebuild(doc, res, hide={value: etype})
        elif action == "unhide":
            new = rebuild(doc, res, unhide={value})
        else:
            raise BadRequest("action must be hide or unhide")
        self._docs.save_result(doc_id, new, saved.revision, owner_id=owner_id)
        return doc, new
