"""Veil API: upload or paste, redact through Mubit, download the redacted file, ask about it, fix it.

Run from backend/: uv run --env-file ../.env uvicorn app.main:app --reload --port 8000
Documents and redactions persist encrypted in PostgreSQL; document text is never logged.
"""

import email
import json
import os
import re
from collections import Counter
from contextlib import asynccontextmanager
from dataclasses import asdict
from email import policy
from pathlib import Path

import pymupdf
import psycopg
from cryptography.fernet import InvalidToken
from evalkit.redact import restore
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

from .auth import User, router as auth_router
from .extract import Document, extract_pdf, extract_text
from .llm import T1_MODEL, T2_MODEL, make_t1_factory, make_t2
from .pdfout import redact_pdf
from .pipeline import PipelineResult, rebuild, run_pipeline
from .storage import MissingDocument, PostgresStore, Snapshot, StaleRevision


@asynccontextmanager
async def lifespan(app: FastAPI):
    store = PostgresStore.from_env()
    try:
        store.initialize()
    except psycopg.Error:
        raise RuntimeError("PostgreSQL is unavailable. Check DATABASE_URL and start the database.") from None
    app.state.store = store
    yield


app = FastAPI(title="Veil", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("VEIL_CORS", "http://localhost:5173,http://127.0.0.1:5173").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)
app.include_router(auth_router)


@app.middleware("http")
async def protect_browser_requests(request: Request, call_next):
    if request.url.path.startswith("/api/"):
        if request.method not in {"GET", "HEAD", "OPTIONS"} and request.headers.get("X-Veil-Request") != "1":
            return JSONResponse(status_code=403, content={"detail": "Missing request protection header."})
        response = await call_next(request)
        if request.url.path.startswith(("/api/auth", "/api/documents")):
            response.headers["Cache-Control"] = "no-store"
        return response
    return await call_next(request)


app.state.t1_factory = make_t1_factory()
app.state.t2 = make_t2()

TEXT_TYPES = (".txt", ".md", ".csv", ".json", ".eml")
IMAGE_TYPES = (".jpg", ".jpeg", ".png", ".heic", ".heif", ".tif", ".tiff", ".webp")
MAX_UPLOAD = 20 * 1024 * 1024


@app.exception_handler(RequestValidationError)
async def invalid_request(request, exc):
    if request.url.path.startswith("/api/auth/"):
        # Never echo submitted passwords in validation responses.
        return JSONResponse(status_code=422, content={"detail": "Enter a valid email and a password of 8 to 128 characters."})
    return await request_validation_exception_handler(request, exc)


@app.exception_handler(MissingDocument)
async def missing_document(_request, _exc):
    return JSONResponse(status_code=404, content={"detail": "Document not found."})


@app.exception_handler(StaleRevision)
async def stale_revision(_request, _exc):
    return JSONResponse(status_code=409, content={"detail": "The document changed. Reload it before trying again."})


@app.exception_handler(psycopg.Error)
async def database_unavailable(_request, _exc):
    return JSONResponse(status_code=503, content={"detail": "Document storage is unavailable. Try again shortly."})


@app.exception_handler(InvalidToken)
async def unreadable_document(_request, _exc):
    return JSONResponse(status_code=503, content={"detail": "Stored content could not be decrypted."})


def _doc(doc_id: str, owner_id: str) -> Document:
    return app.state.store.get(doc_id, owner_id=owner_id).document


def _scanned(doc_id: str, owner_id: str) -> Snapshot:
    saved = app.state.store.get(doc_id, owner_id=owner_id)
    if saved.result is None:
        raise HTTPException(409, "Scan the document first.")
    return saved


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


def _store(doc: Document, owner_id: str) -> dict:
    app.state.store.create(doc, owner_id=owner_id)
    return _doc_payload(doc)


def _ocr(data: bytes, name: str, owner_id: str) -> dict:
    """Scans and photos go through app/ingest (Apple Vision OCR on this Mac). Text only for now:
    no page boxes, so the download is the redacted text, not a redacted image."""
    try:
        from .ingest import OcrError, UnsupportedDocument, extract
    except ImportError:
        raise HTTPException(415, "Reading scans and photos needs the OCR packages. Run uv sync in backend.") from None
    try:
        doc = extract(data)
    except (OcrError, UnsupportedDocument) as exc:
        raise HTTPException(415, str(exc)) from None
    if not doc.text.strip():
        raise HTTPException(400, "No text was found in this file.")
    return _store(extract_text(doc.text, name), owner_id)


@app.get("/api/health")
def health() -> dict:
    app.state.store.healthy()
    on = bool(app.state.t1_factory)
    return {"model": "on" if on else "off", "t1_model": T1_MODEL if on else None,
            "t2_model": T2_MODEL if app.state.t2 else None, "database": "postgresql"}


@app.get("/api/documents/{doc_id}")
def read_document(doc_id: str, user: User) -> dict:
    saved = app.state.store.get(doc_id, owner_id=user["id"])
    return {"document": _doc_payload(saved.document), "revision": saved.revision,
            "result": _result_payload(saved.document, saved.result) if saved.result else None}


@app.delete("/api/documents/{doc_id}", status_code=204)
def delete_document(doc_id: str, user: User) -> Response:
    app.state.store.delete(doc_id, owner_id=user["id"])
    return Response(status_code=204)


@app.post("/api/documents")
async def create_document(user: User, text: str | None = Form(None), file: UploadFile | None = File(None)) -> dict:
    if file is None:
        if not text or not text.strip():
            raise HTTPException(400, "Paste some text or choose a file.")
        return _store(extract_text(text), user["id"])
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
        return _store(doc, user["id"]) if doc.text.strip() else _ocr(data, name, user["id"])  # no text layer: a scanned PDF
    if lower.endswith(".eml"):
        return _store(extract_text(_email_to_text(data), name), user["id"])
    if lower.endswith(TEXT_TYPES):
        return _store(extract_text(data.decode("utf-8", errors="replace"), name), user["id"])
    if lower.endswith(IMAGE_TYPES):
        return _ocr(data, name, user["id"])
    raise HTTPException(415, "This file type is not supported yet. Use PDF, an image, TXT or EML, or paste the text.")


@app.post("/api/documents/{doc_id}/redact")
def redact(doc_id: str, user: User) -> dict:
    saved = app.state.store.get(doc_id, owner_id=user["id"])
    doc = saved.document
    factory = app.state.t1_factory
    res = run_pipeline(doc, t1=factory(doc_id) if factory else None)
    app.state.store.save_result(doc_id, res, saved.revision, owner_id=user["id"])
    return _result_payload(doc, res)


@app.get("/api/documents/{doc_id}/pages/{page}.png")
def page_image(doc_id: str, page: int, user: User, scale: float = 1.5) -> Response:
    doc = _doc(doc_id, user["id"])
    if doc.kind != "pdf" or not doc.source or not 0 <= page < len(doc.pages):
        raise HTTPException(404, "No such page.")
    pix = pymupdf.open(stream=doc.source, filetype="pdf")[page].get_pixmap(matrix=pymupdf.Matrix(scale, scale))
    return Response(pix.tobytes("png"), media_type="image/png")


@app.get("/api/documents/{doc_id}/file")
def redacted_file(doc_id: str, user: User) -> Response:
    saved = _scanned(doc_id, user["id"])
    doc, res = saved.document, saved.result
    stem = Path(doc.filename).stem
    if doc.kind == "pdf" and doc.source:
        return Response(redact_pdf(doc.source, res.boxes), media_type="application/pdf",
                        headers={"Content-Disposition": f'attachment; filename="{stem}-redacted.pdf"'})
    return Response(res.redacted_text, media_type="text/plain; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{stem}-redacted.txt"'})


class Ask(BaseModel):
    question: str


@app.post("/api/documents/{doc_id}/ask")
def ask(doc_id: str, body: Ask, user: User) -> dict:
    res = _scanned(doc_id, user["id"]).result
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
def correct(doc_id: str, body: Correction, user: User) -> dict:
    saved = _scanned(doc_id, user["id"])
    doc, res = saved.document, saved.result
    value = body.text.strip()
    if not value or value not in doc.text:
        raise HTTPException(400, "That text is not in the document.")
    if body.action == "hide":
        new = rebuild(doc, res, hide={value: body.type})
    elif body.action == "unhide":
        new = rebuild(doc, res, unhide={value})
    else:
        raise HTTPException(400, "action must be hide or unhide")
    app.state.store.save_result(doc_id, new, saved.revision, owner_id=user["id"])
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
def open_sample(name: str, user: User) -> dict:
    return _store(extract_pdf(_sample_path(name).read_bytes(), name), user["id"])
