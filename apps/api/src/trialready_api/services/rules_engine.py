"""The compliance decision layer — deterministic on purpose.

This module is the actual product. Everything else (OCR, LLM classification, the
API, the UI) exists to get clean `BinderDocumentSnapshot` data into
`evaluate_binder()` and to surface its `GapReport` output.

It intentionally contains **no LLM calls and no I/O**. A site coordinator's
monitor-visit readiness is a compliance determination with real consequences if
wrong; it must be a pure function of (checklist, documents, today's date) so that:
  1. it's exhaustively unit-testable with plain fixtures,
  2. the same inputs always produce the same output (no model drift between runs),
  3. every output is explainable by pointing at the exact branch that produced it.

See docs/architecture.md, "Why the decision layer is not an agent."
"""

from __future__ import annotations

from datetime import date, timedelta

from trialready_api.schemas.gap_report import (
    BinderDocumentSnapshot,
    GapItem,
    GapReport,
    GapSeverity,
)
from trialready_api.services.document_types import DocumentTypeSpec, ExpiryPolicy, required_document_types

_ACCEPTED = "accepted"
_PENDING_REVIEW = "pending_human_review"
_LIVE_STATUSES = (_ACCEPTED, _PENDING_REVIEW)


def evaluate_binder(
    protocol_id: str,
    documents: list[BinderDocumentSnapshot],
    as_of: date | None = None,
    checklist: tuple[DocumentTypeSpec, ...] | None = None,
) -> GapReport:
    as_of = as_of or date.today()
    checklist = checklist or required_document_types()

    items: list[GapItem] = []
    satisfied_count = 0

    for spec in checklist:
        docs_of_type = [d for d in documents if d.document_type_id == spec.id and d.status in _LIVE_STATUSES]
        item = _evaluate_one(spec, docs_of_type, as_of)
        if item is None:
            satisfied_count += 1
        else:
            items.append(item)

    return GapReport(
        protocol_id=protocol_id,
        generated_at=as_of,
        total_required=len(checklist),
        total_satisfied=satisfied_count,
        items=items,
    )


def _evaluate_one(
    spec: DocumentTypeSpec, docs_of_type: list[BinderDocumentSnapshot], as_of: date
) -> GapItem | None:
    """Returns a GapItem describing the problem, or None if this requirement is clean."""
    if not docs_of_type:
        return GapItem(
            document_type_id=spec.id,
            document_name=spec.name,
            severity=GapSeverity.MISSING,
            detail=f"No {spec.name.lower()} has been uploaded for this protocol.",
            regulatory_basis=spec.regulatory_basis,
        )

    accepted = [d for d in docs_of_type if d.status == _ACCEPTED]
    if not accepted:
        # Every candidate is stuck awaiting human review — extraction confidence was
        # too low to auto-accept. Never silently treat this as satisfied.
        newest = _newest(docs_of_type)
        return GapItem(
            document_type_id=spec.id,
            document_name=spec.name,
            severity=GapSeverity.PENDING_REVIEW,
            detail=(
                f"A {spec.name.lower()} was uploaded but classification confidence was "
                "too low to auto-accept. A coordinator needs to confirm it."
            ),
            regulatory_basis=spec.regulatory_basis,
            existing_document_id=newest.id,
        )

    current = _newest(accepted)

    if spec.version_sensitive and len(accepted) > 1:
        stale = [d for d in accepted if d.id != current.id]
        if stale:
            return GapItem(
                document_type_id=spec.id,
                document_name=spec.name,
                severity=GapSeverity.OUTDATED_VERSION,
                detail=(
                    f"{len(stale)} older accepted version(s) of {spec.name.lower()} are still "
                    "active alongside the newest one. Mark the old version(s) as superseded."
                ),
                regulatory_basis=spec.regulatory_basis,
                existing_document_id=current.id,
            )

    expiry = _resolve_expiry(spec, current)
    if spec.expiry_policy == ExpiryPolicy.PROTOCOL_DEFINED and expiry is None:
        # We can't verify compliance without the date — treat as needing a human,
        # never assume it's fine.
        return GapItem(
            document_type_id=spec.id,
            document_name=spec.name,
            severity=GapSeverity.PENDING_REVIEW,
            detail=(
                f"{spec.name} was accepted but no expiry date was extracted from it. "
                "Confirm the expiry date manually."
            ),
            regulatory_basis=spec.regulatory_basis,
            existing_document_id=current.id,
        )

    if expiry is not None:
        if as_of > expiry:
            return GapItem(
                document_type_id=spec.id,
                document_name=spec.name,
                severity=GapSeverity.EXPIRED,
                detail=f"{spec.name} expired on {expiry.isoformat()}.",
                regulatory_basis=spec.regulatory_basis,
                due_date=expiry,
                existing_document_id=current.id,
            )
        if as_of >= expiry - timedelta(days=spec.alert_window_days):
            return GapItem(
                document_type_id=spec.id,
                document_name=spec.name,
                severity=GapSeverity.EXPIRING_SOON,
                detail=f"{spec.name} expires on {expiry.isoformat()}.",
                regulatory_basis=spec.regulatory_basis,
                due_date=expiry,
                existing_document_id=current.id,
            )

    return None


def _newest(docs: list[BinderDocumentSnapshot]) -> BinderDocumentSnapshot:
    def sort_key(d: BinderDocumentSnapshot) -> date:
        return d.effective_date or d.uploaded_at

    return max(docs, key=sort_key)


def _resolve_expiry(spec: DocumentTypeSpec, doc: BinderDocumentSnapshot) -> date | None:
    if spec.expiry_policy == ExpiryPolicy.NONE:
        return None
    if spec.expiry_policy == ExpiryPolicy.PROTOCOL_DEFINED:
        return doc.expiry_date
    # FIXED_ANNUAL / CUSTOM_DAYS: prefer an explicitly extracted expiry date (e.g. the
    # document itself states one) over the computed policy default.
    if doc.expiry_date is not None:
        return doc.expiry_date
    if doc.effective_date is not None and spec.expiry_days is not None:
        return doc.effective_date + timedelta(days=spec.expiry_days)
    return None
