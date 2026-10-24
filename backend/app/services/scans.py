"""Scans: run the redaction pipeline over a document and keep only the newest result.

Starting a scan reserves a new revision. A scan whose revision is no longer current (a newer scan or a
correction came in) stops early and is not saved. Streamed scans run on a bounded pool shared by the
whole process, so they finish and save even when the client leaves, and a burst of scans queues
instead of starting unbounded threads."""

import queue
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from ..core.errors import StaleRevision, Superseded
from ..core.log import log
from ..domain.pipeline import Emit, PipelineResult, run_pipeline
from ..llm.models import Models
from ..repositories import Storage
from ..repositories.documents import Snapshot

Event = tuple[str, dict]  # (name, data): start, regex, chunk, then done or error


@dataclass
class Scan:
    saved: Snapshot
    owner_id: str
    retry: str | None  # "failed": call T1 only for the parts that failed in the stored run

    @property
    def doc_id(self) -> str:
        return self.saved.document.doc_id


class ScanService:
    def __init__(self, storage: Storage, models: Models, executor: ThreadPoolExecutor, chunk_workers: int = 6):
        self._docs = storage.documents
        self._models = models
        self._executor = executor
        self._chunk_workers = chunk_workers

    def begin(self, doc_id: str, owner_id: str, retry: str | None = None) -> Scan:
        return Scan(self._docs.begin_scan(doc_id, owner_id=owner_id), owner_id, retry)

    def superseded(self, scan: Scan) -> bool:
        return not self._docs.is_current(scan.doc_id, scan.saved.revision, owner_id=scan.owner_id)

    def run(self, scan: Scan, emit: Emit | None = None) -> PipelineResult:
        """Scan and save. Raises Superseded when a newer scan or correction took over meanwhile."""
        doc, saved, models = scan.saved.document, scan.saved, self._models
        stop: Callable[[], bool] = lambda: self.superseded(scan)  # noqa: E731
        res = run_pipeline(doc, t1=models.t1_factory(doc.doc_id) if models.t1_factory else None,
                           max_chars=models.chunk_chars, workers=self._chunk_workers, emit=emit,
                           plan=models.t1_prompt, reuse=saved.result if scan.retry == "failed" else None,
                           stop=stop, corrections=saved.result)
        if stop():
            raise Superseded()
        try:
            self._docs.save_result(doc.doc_id, res, saved.revision, owner_id=scan.owner_id)
        except StaleRevision:
            raise Superseded() from None
        return res

    def stream(self, scan: Scan, on_done: Callable[[PipelineResult], dict], idle: float) -> Iterator[Event | None]:
        """Events as the scan makes progress, and None after `idle` seconds without one (for keep-alives).
        A superseded scan goes quiet and ends with an error event."""
        events: queue.Queue[Event] = queue.Queue()
        models = self._models
        head = {"doc_id": scan.doc_id, "model": "on" if models.on else "off",
                "t1_model": models.t1_model if models.on else None, "t1_prompt": models.t1_prompt}

        def emit(name: str, data: dict) -> None:
            if not self.superseded(scan):
                events.put((name, {**head, **data} if name == "start" else data))

        def work() -> None:
            try:
                events.put(("done", on_done(self.run(scan, emit))))
            except Superseded as exc:
                events.put(("error", {"message": exc.detail}))
            except Exception as exc:  # noqa: BLE001 - reported to the client; the type only, never document text
                log.error("scan failed doc=%s error=%s", scan.doc_id, type(exc).__name__)
                events.put(("error", {"message": f"The scan stopped unexpectedly ({type(exc).__name__}). Try again."}))

        self._executor.submit(work)
        while True:
            try:
                name, data = events.get(timeout=idle)
            except queue.Empty:
                yield None
                continue
            yield name, data
            if name in ("done", "error"):
                return
