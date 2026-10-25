from typing import Annotated

from fastapi import Depends

from app.dependencies import DatabaseDep
from app.modules.documents.repository import DocumentRepository
from app.modules.documents.service import DocumentService


def get_document_repository(db: DatabaseDep) -> DocumentRepository:
    return DocumentRepository(db)


DocumentRepositoryDep = Annotated[DocumentRepository, Depends(get_document_repository)]


def get_document_service(repo: DocumentRepositoryDep) -> DocumentService:
    return DocumentService(repo)


DocumentServiceDep = Annotated[DocumentService, Depends(get_document_service)]
