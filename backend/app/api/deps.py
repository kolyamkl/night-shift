"""What each route gets injected. Everything comes from app.state, set up once in create_app, so tests
can swap a part (the models, the storage) without patching modules."""

from typing import Annotated

from fastapi import Depends, Request

from ..core.config import Config
from ..llm.models import Models
from ..repositories import Storage
from ..services.auth import AuthService
from ..services.chat import ChatService
from ..services.documents import DocumentService
from ..services.review import ReviewService
from ..services.samples import SampleLibrary
from ..services.scans import ScanService

COOKIE = "veil_session"


def get_config(request: Request) -> Config:
    return request.app.state.config


def get_storage(request: Request) -> Storage:
    return request.app.state.storage


def get_models(request: Request) -> Models:
    return request.app.state.models


def get_auth(storage: Annotated[Storage, Depends(get_storage)]) -> AuthService:
    return AuthService(storage.accounts)


def current_user(request: Request, auth: Annotated[AuthService, Depends(get_auth)]) -> dict:
    return auth.user_for(request.cookies.get(COOKIE))


def get_documents(storage: Annotated[Storage, Depends(get_storage)]) -> DocumentService:
    return DocumentService(storage)


def get_scans(request: Request, storage: Annotated[Storage, Depends(get_storage)],
              models: Annotated[Models, Depends(get_models)]) -> ScanService:
    return ScanService(storage, models, request.app.state.scan_executor, request.app.state.config.chunk_workers)


def get_chat(storage: Annotated[Storage, Depends(get_storage)], models: Annotated[Models, Depends(get_models)]) -> ChatService:
    return ChatService(storage, models)


def get_review(storage: Annotated[Storage, Depends(get_storage)]) -> ReviewService:
    return ReviewService(storage)


def get_samples(config: Annotated[Config, Depends(get_config)]) -> SampleLibrary:
    return SampleLibrary(config.samples_dir)


User = Annotated[dict, Depends(current_user)]
Auth = Annotated[AuthService, Depends(get_auth)]
Documents = Annotated[DocumentService, Depends(get_documents)]
Scans = Annotated[ScanService, Depends(get_scans)]
Chat = Annotated[ChatService, Depends(get_chat)]
Review = Annotated[ReviewService, Depends(get_review)]
Samples = Annotated[SampleLibrary, Depends(get_samples)]
ModelsDep = Annotated[Models, Depends(get_models)]
ConfigDep = Annotated[Config, Depends(get_config)]
