"""Turn an upload (pasted text or a file) into a Document, or say why it cannot be read.

PDFs keep their text layer (redaction.document); scans and photos go through OCR (app.ingest, then
redaction.ocr), which gives them word boxes too. Email, text, code and config files are read as
text, as is any file with an unknown extension that is really UTF-8 text (a Dockerfile).
"""

import email
import re
from email import policy
from email.message import EmailMessage
from typing import cast

from app.core.errors import BadRequestError, PayloadTooLargeError, UnsupportedMediaTypeError
from app.redaction.document import Document, extract_pdf, extract_text

MAX_UPLOAD = 20 * 1024 * 1024
TEXT_TYPES = (
    ".txt", ".text", ".md", ".markdown", ".rst", ".csv", ".tsv", ".json", ".jsonl", ".ndjson", ".eml",
    ".log", ".vcf", ".ics", ".srt", ".vtt", ".tex",
    # code
    ".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".vue", ".svelte", ".java", ".kt", ".kts", ".scala",
    ".go", ".rb", ".rs", ".c", ".h", ".cc", ".cpp", ".hpp", ".cs", ".php", ".swift", ".m", ".dart", ".lua",
    ".pl", ".r", ".sql", ".sh", ".bash", ".zsh", ".ps1", ".bat", ".graphql", ".proto",
    # config and markup
    ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf", ".properties", ".xml", ".html", ".htm", ".css",
    ".scss", ".tf",
)  # fmt: skip
IMAGE_TYPES = (".jpg", ".jpeg", ".png", ".heic", ".heif", ".tif", ".tiff", ".webp")

NO_TEXT = "No text was found in this file."
UNSUPPORTED = "This file type is not supported yet. Use PDF, an image, TXT or EML, or paste the text."


def from_pasted(text: str | None) -> Document:
    if not text or not text.strip():
        raise BadRequestError("Paste some text or choose a file.")
    return extract_text(text)


def from_file(data: bytes, filename: str | None) -> Document:
    if len(data) > MAX_UPLOAD:
        raise PayloadTooLargeError("The file is larger than 20 MB.")
    name = filename or "upload"
    lower = name.lower()
    if lower.endswith(".pdf") or data[:5] == b"%PDF-":
        try:
            doc = extract_pdf(data, name)
        except Exception:  # noqa: BLE001 - any parser failure means the same thing to the user
            raise BadRequestError("This PDF could not be read.") from None
        return _ocr(data, name, text_layer=doc if doc.text.strip() else None)  # OCR when any page is a scan
    if lower.endswith(".eml"):
        return _text(_email_to_text(data), name)
    if lower.endswith(TEXT_TYPES):
        return _text(data.decode("utf-8-sig", errors="replace"), name)
    if lower.endswith(IMAGE_TYPES):
        return _ocr(data, name)
    text = _text_or_none(data)  # an unknown extension that is really text, such as a Dockerfile
    if text is not None:
        return _text(text, name)
    raise UnsupportedMediaTypeError(UNSUPPORTED)


def _text(text: str, name: str) -> Document:
    if not text.strip():
        raise BadRequestError(NO_TEXT)
    return extract_text(text, name)


def _email_to_text(raw: bytes) -> str:
    msg = cast(EmailMessage, email.message_from_bytes(raw, policy=policy.default))  # what policy.default builds
    head = "\n".join(f"{h}: {msg[h]}" for h in ("From", "To", "Cc", "Date", "Subject") if msg[h])
    body = msg.get_body(preferencelist=("plain", "html"))
    text = body.get_content() if body else ""
    if body is not None and body.get_content_type() == "text/html":
        text = re.sub(r"<[^>]+>", " ", text)
    return f"{head}\n\n{text}".strip()


def _text_or_none(data: bytes) -> str | None:
    """Text from an upload with an unknown extension: valid UTF-8 with no NUL byte in the first 8 KB."""
    if b"\x00" in data[:8192]:
        return None
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return None


def _ocr(data: bytes, name: str, text_layer: Document | None = None) -> Document:
    """Scans and photos go through app.ingest (Apple Vision OCR on a Mac), then redaction.ocr turns
    them into a PDF with a box for every word, so they get black boxes and a redacted PDF download.
    A PDF with a text layer is kept as it is unless ingest finds a scanned page in it, such as a scan
    with a page-number stamp: its image would never be read."""
    try:
        from app.ingest import OcrError, UnsupportedDocument, scanned_pages  # noqa: PLC0415 - optional packages
        from app.redaction.ocr import document_from_ocr  # noqa: PLC0415
    except ImportError:
        if text_layer is not None:
            return text_layer
        raise UnsupportedMediaTypeError(
            "Reading scans and photos needs the OCR packages. Run uv sync in backend."
        ) from None
    if text_layer is not None:
        try:
            scans = scanned_pages(data)
        except UnsupportedDocument:  # pdfium cannot open what PyMuPDF did: keep PyMuPDF's reading
            scans = []
        if not scans:
            return text_layer
    try:
        doc = document_from_ocr(data, name)
    except (OcrError, UnsupportedDocument) as exc:
        raise UnsupportedMediaTypeError(str(exc)) from None
    if not doc.text.strip():
        raise BadRequestError(NO_TEXT)
    return doc
