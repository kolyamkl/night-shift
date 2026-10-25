"""Files made from a stored document: a page as an image for review, and the redacted download.

A PDF downloads as a truly redacted PDF (redaction.pdf: the text under each box is removed); a text
document downloads as the redacted text.
"""

from dataclasses import dataclass
from pathlib import Path

import pymupdf

from app.core.errors import NotFoundError
from app.modules.documents.service import DocumentService
from app.redaction.pdf import redact_pdf


@dataclass(frozen=True)
class FileOut:
    content: bytes | str
    media_type: str
    filename: str


class FileService:
    def __init__(self, documents: DocumentService) -> None:
        self.documents = documents

    def page_png(self, doc_id: str, page: int, scale: float, *, owner_id: str) -> bytes:
        doc = self.documents.get(doc_id, owner_id=owner_id)
        if doc.kind != "pdf" or not doc.source or not 0 <= page < len(doc.pages):
            raise NotFoundError("No such page.")
        pix = pymupdf.open(stream=doc.source, filetype="pdf")[page].get_pixmap(matrix=pymupdf.Matrix(scale, scale))
        return pix.tobytes("png")

    def redacted(self, doc_id: str, *, owner_id: str) -> FileOut:
        saved = self.documents.get_scanned(doc_id, owner_id=owner_id)
        doc, res = saved.document, saved.result
        stem = Path(doc.filename).stem
        if doc.kind == "pdf" and doc.source:
            return FileOut(redact_pdf(doc.source, res.boxes), "application/pdf", f"{stem}-redacted.pdf")
        return FileOut(res.redacted_text, "text/plain; charset=utf-8", f"{stem}-redacted.txt")
