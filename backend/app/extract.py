"""Deprecated import path: documents are read in app.redaction.document.

Kept for scripts/samples/make_tenancy.py; remove once it imports app.redaction.document.
"""

from app.redaction.document import Document, Word, extract_pdf, extract_text

__all__ = ["Document", "Word", "extract_pdf", "extract_text"]
