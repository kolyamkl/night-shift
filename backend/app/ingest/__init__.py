"""Local document ingestion: PDF text layers, and Apple Vision OCR for scans and photos.

Nothing here calls an LLM or the network, so a document's personal data stays on this
machine until the redacted text is sent to T1.
"""

from .extract import extract, scanned_pages
from .fixes import fix_identifiers
from .types import ExtractedDocument, Fix, Line, OcrError, Page, UnsupportedDocument

__all__ = ["extract", "scanned_pages", "fix_identifiers", "ExtractedDocument", "Fix", "Line", "OcrError", "Page", "UnsupportedDocument"]
