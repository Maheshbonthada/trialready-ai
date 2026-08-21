"""Orchestrates one uploaded file through OCR -> classification -> persistence.

This is the "pipeline of agent skills" described in docs/architecture.md: each
step is a small, independently testable unit; this function just sequences them
and applies the one policy decision that matters — the confidence gate.
"""

from __future__ import annotations

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from trialready_api.agents.classification_agent import DocumentClassifier
from trialready_api.agents.ocr_client import DocumentOcrClient
from trialready_api.config import Settings
from trialready_api.db.models import BinderDocument, DocumentStatus
from trialready_api.services import audit_service
from trialready_api.services.blob_storage import BlobStore
from trialready_api.services.document_types import get_document_type, required_document_types

logger = structlog.get_logger(__name__)


async def ingest_document(
    *,
    db: AsyncSession,
    protocol_id: str,
    file_bytes: bytes,
    original_filename: str,
    content_type: str,
    uploaded_by: str,
    settings: Settings,
    ocr_client: DocumentOcrClient,
    classifier: DocumentClassifier,
    blob_store: BlobStore,
    request_id: str | None = None,
) -> BinderDocument:
    blob_path = await blob_store.upload(
        container=settings.binder_documents_container,
        path_hint=f"{protocol_id}/incoming",
        data=file_bytes,
        content_type=content_type,
    )

    ocr_result = await ocr_client.extract(file_bytes, content_type)
    classification = await classifier.classify(
        ocr_text=ocr_result.full_text,
        kv_pairs=ocr_result.key_value_pairs,
        candidate_types=list(required_document_types()),
    )

    resolved_type_id = classification.document_type_id
    known_type = get_document_type(resolved_type_id) if resolved_type_id else None

    is_confident = (
        known_type is not None and classification.confidence >= settings.classification_min_confidence
    )
    status = DocumentStatus.ACCEPTED if is_confident else DocumentStatus.PENDING_HUMAN_REVIEW

    document = BinderDocument(
        protocol_id=protocol_id,
        document_type_id=resolved_type_id or "unclassified",
        original_filename=original_filename,
        blob_path=blob_path,
        status=status,
        classification_confidence=classification.confidence,
        extracted_effective_date=classification.effective_date,
        extracted_expiry_date=classification.expiry_date,
        extracted_signer_name=classification.signer_name,
        extracted_signed_date=classification.signed_date,
        version_label=classification.version_label,
        uploaded_by=uploaded_by,
    )
    db.add(document)
    await db.flush()  # assigns document.id within the open transaction

    await audit_service.record(
        db,
        actor=uploaded_by,
        action="document.classified",
        entity_type="binder_document",
        entity_id=str(document.id),
        details={
            "resolved_type_id": resolved_type_id,
            "confidence": classification.confidence,
            "status": status.value,
            "rationale": classification.rationale,
        },
        request_id=request_id,
    )

    if not is_confident:
        logger.info(
            "document.pending_human_review",
            document_id=str(document.id),
            confidence=classification.confidence,
            proposed_type=resolved_type_id,
        )

    await db.commit()
    await db.refresh(document)
    return document
