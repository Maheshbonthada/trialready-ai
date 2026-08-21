from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from trialready_api.agents.classification_agent import DocumentClassifier
from trialready_api.agents.ocr_client import DocumentOcrClient
from trialready_api.config import Settings, get_settings
from trialready_api.core.security import AuthenticatedUser, get_current_user
from trialready_api.db.models import BinderDocument, Protocol
from trialready_api.db.session import get_db_session
from trialready_api.deps import get_classifier, get_ocr_client
from trialready_api.deps import get_blob_store as _get_blob_store
from trialready_api.schemas.api import BinderDocumentOut
from trialready_api.services.blob_storage import BlobStore
from trialready_api.services.document_ingestion import ingest_document

router = APIRouter(prefix="/api/v1/protocols/{protocol_id}/documents", tags=["documents"])

_MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25MB — comfortably above a scanned multi-page PDF


@router.post("", response_model=BinderDocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_document(
    protocol_id: uuid.UUID,
    file: UploadFile,
    db: AsyncSession = Depends(get_db_session),
    user: AuthenticatedUser = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    ocr_client: DocumentOcrClient = Depends(get_ocr_client),
    classifier: DocumentClassifier = Depends(get_classifier),
    blob_store: BlobStore = Depends(_get_blob_store),
) -> BinderDocument:
    protocol = await db.get(Protocol, protocol_id)
    if protocol is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Protocol not found")

    file_bytes = await file.read(_MAX_UPLOAD_BYTES + 1)
    if len(file_bytes) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File too large")
    if not file_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file")

    return await ingest_document(
        db=db,
        protocol_id=str(protocol_id),
        file_bytes=file_bytes,
        original_filename=file.filename or "unnamed",
        content_type=file.content_type or "application/octet-stream",
        uploaded_by=user.subject,
        settings=settings,
        ocr_client=ocr_client,
        classifier=classifier,
        blob_store=blob_store,
    )


@router.get("", response_model=list[BinderDocumentOut])
async def list_documents(
    protocol_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    user: AuthenticatedUser = Depends(get_current_user),
) -> list[BinderDocument]:
    result = await db.execute(select(BinderDocument).where(BinderDocument.protocol_id == protocol_id))
    return list(result.scalars().all())
