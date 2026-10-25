"""Scanning a document: run the redaction pipeline and keep the newest result only.

A scan first reserves a revision (begin_scan). A later scan or correction moves the revision on, so
an older scan sees it is superseded: its remaining chunks make no T1 call and its result is not
saved. ?retry=failed reuses the stored result's chunks that succeeded under the same chunk plan, so
T1 is called only for the chunks that failed or were off.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from app.llm.models import Models
from app.modules.documents.repository import DocumentRepository, Snapshot, StaleRevision
from app.modules.documents.schemas import ScanResult
from app.redaction.pipeline import Emit, run_pipeline

Retry = Literal["failed"] | None
SUPERSEDED = "A newer scan of this document started, so this one stopped."


class Superseded(Exception):
    """A newer scan or correction replaced this scan's reserved revision."""


@dataclass(frozen=True)
class Scan:
    saved: Snapshot  # the document as it was when the scan reserved its revision
    superseded: Callable[[], bool]  # True once a newer scan or correction took the document


class ScanService:
    def __init__(self, repo: DocumentRepository, models: Models) -> None:
        self.repo = repo
        self.models = models

    def start(self, doc_id: str, *, owner_id: str) -> Scan:
        saved = self.repo.begin_scan(doc_id, owner_id=owner_id)
        return Scan(saved, lambda: not self.repo.is_current(doc_id, saved.revision, owner_id=owner_id))

    def run(self, scan: Scan, *, owner_id: str, retry: Retry = None, emit: Emit | None = None) -> ScanResult:
        """Persist the newest scan only. Failed-part retries reuse the encrypted saved chunk results."""
        saved, models = scan.saved, self.models
        doc = saved.document
        factory = models.t1_factory
        res = run_pipeline(doc, t1=factory(doc.doc_id) if factory else None, max_chars=models.chunk_chars,
                           emit=emit, plan=models.t1_prompt, reuse=saved.result if retry == "failed" else None,
                           stop=scan.superseded, corrections=saved.result)
        if scan.superseded():
            raise Superseded
        try:
            self.repo.save_result(doc.doc_id, res, saved.revision, owner_id=owner_id)
        except StaleRevision:
            raise Superseded from None
        return ScanResult.of(doc, res, "on" if models.t1_on else "off")
