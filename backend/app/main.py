"""Veil API: upload or paste, redact through Mubit, download the redacted file, ask about it, fix it.

Run: MUBIT_API_KEY=mbt_... uv run uvicorn app.main:app --reload --port 8000
Documents live in memory for the session; nothing is written to disk and document text is never logged.
"""

import email
import json
import os
import re
from collections import Counter
from dataclasses import asdict
from email import policy
from pathlib import Path

import pymupdf
from evalkit.redact import restore
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel

from .extract import Document, extract_pdf, extract_text
from .llm import T1_MODEL, T2_MODEL, make_t1_factory, make_t2
from .pdfout import redact_pdf
from .pipeline import PipelineResult, rebuild, run_pipeline

app = FastAPI(title="Veil")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("VEIL_CORS", "http://localhost:5173,http://127.0.0.1:5173").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)
app.state.t1_factory = make_t1_factory()
app.state.t2 = make_t2()

DOCS: dict[str, Document] = {}
RESULTS: dict[str, PipelineResult] = {}
TEXT_TYPES = (".txt", ".md", ".csv", ".json", ".eml")
IMAGE_TYPES = (".jpg", ".jpeg", ".png", ".heic", ".heif", ".tif", ".tiff", ".webp")
MAX_UPLOAD = 20 * 1024 * 1024


def _doc(doc_id: str) -> Document:
    if doc_id not in DOCS:
        raise HTTPException(404, "Document not found. Upload it again.")
    return DOCS[doc_id]


def _result(doc_id: str) -> PipelineResult:
    _doc(doc_id)
    if doc_id not in RESULTS:
        raise HTTPException(409, "Scan the document first.")
    return RESULTS[doc_id]


def _doc_payload(doc: Document) -> dict:
    return {"doc_id": doc.doc_id, "kind": doc.kind, "filename": doc.filename, "text": doc.text,
            "pages": [{"width": w, "height": h} for w, h in doc.pages]}


def _result_payload(doc: Document, res: PipelineResult) -> dict:
    return {
        "doc_id": doc.doc_id,
        "redacted_text": res.redacted_text,
        "entities": [{"start": s.start, "end": s.end, "text": s.text, "type": s.type,
                      "placeholder": res.vault.placeholder_for(s.text, s.type)} for s in res.spans],
        "boxes": [asdict(b) for b in res.boxes],
        "chunks": [asdict(c) for c in res.chunks],
        "stats": res.stats,
        "model": "on" if app.state.t1_factory else "off",
    }


def _email_to_text(raw: bytes) -> str:
    msg = email.message_from_bytes(raw, policy=policy.default)
    head = "\n".join(f"{h}: {msg[h]}" for h in ("From", "To", "Cc", "Date", "Subject") if msg[h])
    body = msg.get_body(preferencelist=("plain", "html"))
    text = body.get_content() if body else ""
    if body is not None and body.get_content_type() == "text/html":
        text = re.sub(r"<[^>]+>", " ", text)
    return f"{head}\n\n{text}".strip()


def _store(doc: Document) -> dict:
    DOCS[doc.doc_id] = doc
    return _doc_payload(doc)


def _ocr(data: bytes, name: str, text_layer: Document | None = None) -> dict:
    """Scans and photos go through app/ingest (Apple Vision OCR on this Mac), then app/ocrdoc turns
    them into a PDF with a box for every word, so they get black boxes and a redacted PDF download.
    A PDF with a text layer (text_layer, read by extract.py) is kept as it is unless ingest finds a
    scanned page in it, such as a scan with a page-number stamp: its image would never be read."""
    try:
        from .ingest import OcrError, UnsupportedDocument, scanned_pages
        from .ocrdoc import document_from_ocr
    except ImportError:
        if text_layer is not None:
            return _store(text_layer)
        raise HTTPException(415, "Reading scans and photos needs the OCR packages. Run uv sync in backend.") from None
    if text_layer is not None:
        try:
            scans = scanned_pages(data)
        except UnsupportedDocument:  # pdfium cannot open what PyMuPDF did: keep PyMuPDF's reading
            scans = []
        if not scans:
            return _store(text_layer)
    try:
        doc = document_from_ocr(data, name)
    except (OcrError, UnsupportedDocument) as exc:
        raise HTTPException(415, str(exc)) from None
    if not doc.text.strip():
        raise HTTPException(400, "No text was found in this file.")
    return _store(doc)


@app.get("/api/health")
def health() -> dict:
    on = bool(app.state.t1_factory)
    return {"model": "on" if on else "off", "t1_model": T1_MODEL if on else None,
            "t2_model": T2_MODEL if app.state.t2 else None}


@app.post("/api/documents")
async def create_document(text: str | None = Form(None), file: UploadFile | None = File(None)) -> dict:
    if file is None:
        if not text or not text.strip():
            raise HTTPException(400, "Paste some text or choose a file.")
        return _store(extract_text(text))
    data = await file.read()
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, "The file is larger than 20 MB.")
    name = file.filename or "upload"
    lower = name.lower()
    if lower.endswith(".pdf") or data[:5] == b"%PDF-":
        try:
            doc = extract_pdf(data, name)
        except Exception:
            raise HTTPException(400, "This PDF could not be read.") from None
        return _ocr(data, name, text_layer=doc if doc.text.strip() else None)  # OCR when any page is a scan
    if lower.endswith(".eml"):
        return _store(extract_text(_email_to_text(data), name))
    if lower.endswith(TEXT_TYPES):
        return _store(extract_text(data.decode("utf-8", errors="replace"), name))
    if lower.endswith(IMAGE_TYPES):
        return _ocr(data, name)
    raise HTTPException(415, "This file type is not supported yet. Use PDF, an image, TXT or EML, or paste the text.")


@app.post("/api/documents/{doc_id}/redact")
def redact(doc_id: str) -> dict:
    doc = _doc(doc_id)
    factory = app.state.t1_factory
    res = run_pipeline(doc, t1=factory(doc_id) if factory else None)
    RESULTS[doc_id] = res
    return _result_payload(doc, res)


@app.get("/api/documents/{doc_id}/pages/{page}.png")
def page_image(doc_id: str, page: int, scale: float = 1.5) -> Response:
    doc = _doc(doc_id)
    if doc.kind != "pdf" or not doc.source or not 0 <= page < len(doc.pages):
        raise HTTPException(404, "No such page.")
    pix = pymupdf.open(stream=doc.source, filetype="pdf")[page].get_pixmap(matrix=pymupdf.Matrix(scale, scale))
    return Response(pix.tobytes("png"), media_type="image/png")


@app.get("/api/documents/{doc_id}/file")
def redacted_file(doc_id: str) -> Response:
    doc, res = _doc(doc_id), _result(doc_id)
    stem = Path(doc.filename).stem
    if doc.kind == "pdf" and doc.source:
        return Response(redact_pdf(doc.source, res.boxes), media_type="application/pdf",
                        headers={"Content-Disposition": f'attachment; filename="{stem}-redacted.pdf"'})
    return Response(res.redacted_text, media_type="text/plain; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{stem}-redacted.txt"'})


class Ask(BaseModel):
    question: str


@app.post("/api/documents/{doc_id}/ask")
def ask(doc_id: str, body: Ask) -> dict:
    res = _result(doc_id)
    if not app.state.t2:
        raise HTTPException(503, "The chat model is off. Start the backend with MUBIT_API_KEY set.")
    try:
        raw, mreq = app.state.t2(body.question, res.redacted_text)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"The model did not answer: {exc}") from None
    answer, unknown = restore(raw, res.vault)
    return {"answer": answer, "answer_with_placeholders": raw, "sent_text": res.redacted_text,
            "unknown_placeholders": unknown, "mreq_id": mreq}


class Correction(BaseModel):
    action: str  # "hide" or "unhide"
    text: str
    type: str = "CUSTOM"


@app.post("/api/documents/{doc_id}/corrections")
def correct(doc_id: str, body: Correction) -> dict:
    doc, res = _doc(doc_id), _result(doc_id)
    value = body.text.strip()
    if not value or value not in doc.text:
        raise HTTPException(400, "That text is not in the document.")
    if body.action == "hide":
        new = rebuild(doc, res, hide={value: body.type})
    elif body.action == "unhide":
        new = rebuild(doc, res, unhide={value})
    else:
        raise HTTPException(400, "action must be hide or unhide")
    RESULTS[doc_id] = new
    return _result_payload(doc, new)


def _samples_dir() -> Path:
    default = Path(__file__).resolve().parents[2] / "data" / "synthetic" / "pdfs"
    return Path(os.environ.get("VEIL_SAMPLES_DIR", default))


LABEL_WORDS = {"nda": "NDA", "cv": "CV", "hr": "HR", "gov": "government"}


def _label(name: str) -> str:
    words = re.sub(r"^\d+_", "", Path(name).stem).split("_")
    text = " ".join(LABEL_WORDS.get(w, w) for w in words)
    return text[0].upper() + text[1:]


def _sample_path(name: str) -> Path:
    path = _samples_dir() / name
    if "/" in name or ".." in name or not path.is_file() or path.suffix != ".pdf":
        raise HTTPException(404, "No such sample.")
    return path


def _sample_card(path: Path) -> dict:
    """What a sample card shows: the document's own title, its pages and how many personal values it holds."""
    label = _label(path.name)
    card = {"name": path.name, "label": label, "title": label, "kind": re.sub(r"^\d+_", "", path.stem),
            "pages": len(pymupdf.open(path)), "values": None, "types": {}}
    gold = path.with_suffix(".gold.json")
    if gold.is_file():
        data = json.loads(gold.read_text())
        card["title"] = data.get("text", "").split("\n", 1)[0].strip() or label
        card["kind"] = data.get("doc_type", card["kind"])
        card["values"] = len(data.get("entities", []))
        card["types"] = dict(Counter(e["type"] for e in data.get("entities", [])))
    return card


@app.get("/api/samples")
def samples() -> list[dict]:
    d = _samples_dir()
    if not d.is_dir():
        return []
    return [_sample_card(p) for p in sorted(d.glob("*.pdf"))]


@app.get("/api/samples/{name}/thumb.png")
def sample_thumb(name: str, width: int = 120) -> Response:
    page = pymupdf.open(_sample_path(name))[0]
    pix = page.get_pixmap(matrix=pymupdf.Matrix(width / page.rect.width, width / page.rect.width))
    pix.gamma_with(0.35)  # darken: at thumbnail size, thin text strokes would otherwise fade to white
    return Response(pix.tobytes("png"), media_type="image/png", headers={"Cache-Control": "max-age=3600"})


@app.post("/api/samples/{name}")
def open_sample(name: str) -> dict:
    return _store(extract_pdf(_sample_path(name).read_bytes(), name))
