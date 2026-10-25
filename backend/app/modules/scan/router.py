"""/api/documents/{doc_id}/redact: scan a document, in one response or as a live event stream."""

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.core.errors import ConflictError
from app.dependencies import ModelsDep
from app.modules.auth.dependencies import CurrentUser
from app.modules.documents.dependencies import DocumentRepositoryDep
from app.modules.documents.schemas import ScanResult
from app.modules.scan.service import SUPERSEDED, Retry, ScanService, Superseded
from app.modules.scan.stream import SSE_HEADERS, scan_events

router = APIRouter(prefix="/api/documents")


def get_scan_service(repo: DocumentRepositoryDep, models: ModelsDep) -> ScanService:
    return ScanService(repo, models)


ScanServiceDep = Annotated[ScanService, Depends(get_scan_service)]


@router.post("/{doc_id}/redact")
def redact(doc_id: str, user: CurrentUser, scans: ScanServiceDep, retry: Retry = None) -> ScanResult:
    scan = scans.start(doc_id, owner_id=user.id)
    try:
        return scans.run(scan, owner_id=user.id, retry=retry)
    except Superseded:
        raise ConflictError(SUPERSEDED) from None


@router.post("/{doc_id}/redact/stream")
def redact_stream(doc_id: str, user: CurrentUser, scans: ScanServiceDep, retry: Retry = None) -> StreamingResponse:
    """?retry=failed: call T1 only for the chunks that failed (or were off) in the stored run, if it
    has the same chunk plan; other chunks are sent at once from that run. Otherwise a full run."""
    scan = scans.start(doc_id, owner_id=user.id)
    return StreamingResponse(scan_events(scans, scan, owner_id=user.id, retry=retry), headers=SSE_HEADERS)
