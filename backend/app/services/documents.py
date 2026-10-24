"""A user's documents: add, list, open, review status, delete, and the files made from them."""

from dataclasses import dataclass
from pathlib import Path

import pymupdf

from ..core.errors import Conflict, NotFound
from ..domain.extract import Document
from ..domain.pdfout import redact_pdf
from ..repositories import Storage
from ..repositories.documents import Snapshot
from . import ingest


@dataclass
class FileOut:
    content: bytes | str
    media_type: str
    filename: str


class DocumentService:
    def __init__(self, storage: Storage):
        self._docs = storage.documents
        self._chat = storage.chat

    def add(self, doc: Document, owner_id: str) -> Document:
        self._docs.create(doc, owner_id=owner_id)
        return doc

    def add_paste(self, text: str | None, owner_id: str) -> Document:
        return self.add(ingest.from_paste(text), owner_id)

    def add_upload(self, data: bytes, name: str, owner_id: str) -> Document:
        return self.add(ingest.from_upload(data, name), owner_id)

    def summaries(self, owner_id: str) -> list[dict]:
        """Summaries only, no document text: last updated first, at most 200."""
        return self._docs.list_documents(owner_id=owner_id)

    def get(self, doc_id: str, owner_id: str) -> Snapshot:
        return self._docs.get(doc_id, owner_id=owner_id)

    def scanned(self, doc_id: str, owner_id: str) -> Snapshot:
        saved = self.get(doc_id, owner_id)
        if saved.result is None:
            raise Conflict("Scan the document first.")
        return saved

    def turns(self, doc_id: str, owner_id: str) -> list[dict]:
        return self._chat.turns(doc_id, owner_id=owner_id)

    def set_status(self, doc_id: str, status: str, owner_id: str) -> str:
        return self._docs.set_status(doc_id, status, owner_id=owner_id)

    def delete(self, doc_id: str, owner_id: str) -> None:
        self._docs.delete(doc_id, owner_id=owner_id)

    def page_image(self, doc_id: str, page: int, scale: float, owner_id: str) -> bytes:
        doc = self.get(doc_id, owner_id).document
        if doc.kind != "pdf" or not doc.source or not 0 <= page < len(doc.pages):
            raise NotFound("No such page.")
        pix = pymupdf.open(stream=doc.source, filetype="pdf")[page].get_pixmap(matrix=pymupdf.Matrix(scale, scale))
        return pix.tobytes("png")

    def redacted_file(self, doc_id: str, owner_id: str) -> FileOut:
        saved = self.scanned(doc_id, owner_id)
        doc, res = saved.document, saved.result
        stem = Path(doc.filename).stem
        if doc.kind == "pdf" and doc.source:
            return FileOut(redact_pdf(doc.source, res.boxes), "application/pdf", f"{stem}-redacted.pdf")
        return FileOut(res.redacted_text, "text/plain; charset=utf-8", f"{stem}-redacted.txt")
