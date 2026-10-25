"""/api/samples: list the sample documents, their thumbnails, and open one as the caller's document."""

from typing import Annotated

from fastapi import APIRouter, Depends, Response

from app.dependencies import SettingsDep
from app.modules.auth.dependencies import CurrentUser
from app.modules.documents.dependencies import DocumentServiceDep
from app.modules.documents.schemas import DocumentOut
from app.modules.samples.schemas import SampleCard
from app.modules.samples.service import SampleService

router = APIRouter(prefix="/api/samples")


def get_sample_service(settings: SettingsDep) -> SampleService:
    return SampleService(settings.samples_dir)


SampleServiceDep = Annotated[SampleService, Depends(get_sample_service)]


@router.get("")
def samples(service: SampleServiceDep) -> list[SampleCard]:
    return service.cards()


@router.get("/{name}/thumb.png")
def sample_thumb(name: str, service: SampleServiceDep, width: int = 120) -> Response:
    return Response(service.thumbnail(name, width), media_type="image/png", headers={"Cache-Control": "max-age=3600"})


@router.post("/{name}")
def open_sample(name: str, user: CurrentUser, service: SampleServiceDep, documents: DocumentServiceDep) -> DocumentOut:
    return documents.create(service.document(name), owner_id=user.id)
