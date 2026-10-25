"""/api/documents/{doc_id}/pages/{page}.png and /api/documents/{doc_id}/file."""

from fastapi import APIRouter, Response

from app.modules.auth.dependencies import CurrentUser
from app.modules.documents.dependencies import DocumentServiceDep
from app.modules.files.service import FileService

router = APIRouter(prefix="/api/documents")


@router.get("/{doc_id}/pages/{page}.png")
def page_image(
    doc_id: str, page: int, user: CurrentUser, documents: DocumentServiceDep, scale: float = 1.5
) -> Response:
    png = FileService(documents).page_png(doc_id, page, scale, owner_id=user.id)
    return Response(png, media_type="image/png")


@router.get("/{doc_id}/file")
def redacted_file(doc_id: str, user: CurrentUser, documents: DocumentServiceDep) -> Response:
    out = FileService(documents).redacted(doc_id, owner_id=user.id)
    return Response(
        out.content,
        media_type=out.media_type,
        headers={"Content-Disposition": f'attachment; filename="{out.filename}"'},
    )
