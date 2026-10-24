"""/api/documents/{id}/redact: run a scan, at once or as server-sent events; and review corrections."""

import json
from typing import Literal

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from ..deps import ModelsDep, Review, Scans, User
from ..schemas import Correction, result_out

router = APIRouter(prefix="/api/documents/{doc_id}", tags=["scans"])
Retry = Literal["failed"] | None
PING_SECONDS = 5.0  # a comment line while waiting, so proxies and the browser keep the stream open
SSE_HEADERS = {"Content-Type": "text/event-stream", "Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


@router.post("/redact")
def redact(doc_id: str, user: User, scans: Scans, models: ModelsDep, retry: Retry = None) -> dict:
    scan = scans.begin(doc_id, user["id"], retry)
    res = scans.run(scan)  # Superseded becomes a 409 with its message
    return result_out(scan.saved.document, res, models)


@router.post("/redact/stream")
def redact_stream(doc_id: str, user: User, scans: Scans, models: ModelsDep, retry: Retry = None) -> StreamingResponse:
    """?retry=failed: call T1 only for the chunks that failed (or were off) in the stored run, if it
    has the same chunk plan; other chunks are sent at once from that run. Otherwise a full run."""
    scan = scans.begin(doc_id, user["id"], retry)
    doc = scan.saved.document

    def lines():
        for event in scans.stream(scan, lambda res: result_out(doc, res, models), PING_SECONDS):
            yield ": ping\n\n" if event is None else f"event: {event[0]}\ndata: {json.dumps(event[1])}\n\n"

    return StreamingResponse(lines(), headers=SSE_HEADERS)


@router.post("/corrections")
def correct(doc_id: str, body: Correction, user: User, review: Review, models: ModelsDep) -> dict:
    doc, new = review.correct(doc_id, body.action, body.text, body.type, user["id"])
    return result_out(doc, new, models)
