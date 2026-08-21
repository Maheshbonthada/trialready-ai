"""Runs the rules engine against a protocol's current binder and persists the result."""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from trialready_api.db.models import BinderDocument, GapCheckRun
from trialready_api.schemas.gap_report import BinderDocumentSnapshot, GapReport
from trialready_api.services import audit_service
from trialready_api.services.rules_engine import evaluate_binder


async def run_gap_check(
    db: AsyncSession, *, protocol_id: str, triggered_by: str, request_id: str | None = None
) -> GapReport:
    result = await db.execute(select(BinderDocument).where(BinderDocument.protocol_id == protocol_id))
    documents = result.scalars().all()

    snapshots = [
        BinderDocumentSnapshot(
            id=str(doc.id),
            document_type_id=doc.document_type_id,
            status=doc.status.value,
            classification_confidence=(
                float(doc.classification_confidence) if doc.classification_confidence is not None else None
            ),
            effective_date=doc.extracted_effective_date,
            expiry_date=doc.extracted_expiry_date,
            version_label=doc.version_label,
            uploaded_at=doc.uploaded_at.date(),
        )
        for doc in documents
    ]

    report = evaluate_binder(protocol_id=protocol_id, documents=snapshots, as_of=date.today())

    run = GapCheckRun(
        protocol_id=protocol_id,
        triggered_by=triggered_by,
        report_json=report.model_dump(mode="json"),
    )
    db.add(run)

    await audit_service.record(
        db,
        actor=triggered_by,
        action="gap_check.run",
        entity_type="protocol",
        entity_id=protocol_id,
        details={
            "total_required": report.total_required,
            "total_satisfied": report.total_satisfied,
            "monitor_visit_ready": report.is_monitor_visit_ready,
        },
        request_id=request_id,
    )

    await db.commit()
    return report
