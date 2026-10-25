"""The live scan as server-sent events: start, regex, one chunk per chunk as each finishes, then done
or error. Event names, their order and their data are the frontend's contract (frontend/src/scan.ts).

The scan runs in its own thread, so it finishes and stores its result even if the client leaves. A
scan replaced by a newer one goes quiet and ends with an error event. While waiting, a comment line
goes out every PING_SECONDS, so proxies and the browser keep the stream open.
"""

import json
import logging
import queue
import threading
from collections.abc import Iterator
from typing import Any

from app.core.logging import in_current_context, log_event
from app.modules.scan.service import SUPERSEDED, Retry, Scan, ScanService, Superseded

PING_SECONDS = 5.0
SSE_HEADERS = {"Content-Type": "text/event-stream", "Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
END_EVENTS = ("done", "error")

log = logging.getLogger("veil.scan")


def sse(name: str, data: dict[str, Any]) -> str:
    return f"event: {name}\ndata: {json.dumps(data)}\n\n"


def scan_events(service: ScanService, scan: Scan, *, owner_id: str, retry: Retry) -> Iterator[str]:
    doc = scan.saved.document
    models = service.models
    events: queue.Queue[tuple[str, dict[str, Any]]] = queue.Queue()
    head = {
        "doc_id": doc.doc_id,
        "model": "on" if models.t1_on else "off",
        "t1_model": models.t1_model if models.t1_on else None,
        "t1_prompt": models.t1_prompt,
    }

    def emit(name: str, data: dict[str, Any]) -> None:
        if not scan.superseded():
            events.put((name, {**head, **data} if name == "start" else data))

    def work() -> None:
        try:
            result = service.run(scan, owner_id=owner_id, retry=retry, emit=emit)
            events.put(("done", result.model_dump()))
        except Superseded:
            events.put(("error", {"message": SUPERSEDED}))
        except Exception as exc:  # noqa: BLE001 - reported to the client; the type only, never document text
            log_event(log, "scan_failed", logging.ERROR, doc=doc.doc_id, error=type(exc).__name__)
            events.put(("error", {"message": f"The scan stopped unexpectedly ({type(exc).__name__}). Try again."}))

    threading.Thread(target=in_current_context(work), name=f"scan-{doc.doc_id}", daemon=True).start()
    while True:
        try:
            name, data = events.get(timeout=PING_SECONDS)
        except queue.Empty:
            yield ": ping\n\n"
            continue
        yield sse(name, data)
        if name in END_EVENTS:
            return
