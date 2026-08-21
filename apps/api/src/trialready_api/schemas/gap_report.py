"""Pydantic schemas for the gap-check domain.

`BinderDocumentSnapshot` is intentionally decoupled from the SQLAlchemy `BinderDocument`
model — the rules engine takes plain, immutable snapshots so it stays a pure function
that's trivial to unit test with in-memory fixtures and has zero knowledge of the DB
or Azure. See services/rules_engine.py.
"""

from __future__ import annotations

from datetime import date
from enum import Enum

from pydantic import BaseModel


class GapSeverity(str, Enum):
    MISSING = "missing"
    EXPIRED = "expired"
    EXPIRING_SOON = "expiring_soon"
    OUTDATED_VERSION = "outdated_version"
    PENDING_REVIEW = "pending_review"  # low-confidence classification awaiting a human


class BinderDocumentSnapshot(BaseModel):
    """Point-in-time view of one uploaded document, as understood after extraction."""

    id: str
    document_type_id: str
    status: str  # mirrors db.models.DocumentStatus values
    classification_confidence: float | None = None
    effective_date: date | None = None
    expiry_date: date | None = None
    version_label: str | None = None
    uploaded_at: date


class GapItem(BaseModel):
    document_type_id: str
    document_name: str
    severity: GapSeverity
    detail: str
    regulatory_basis: str
    due_date: date | None = None  # when this becomes/became a hard problem
    existing_document_id: str | None = None


class GapReport(BaseModel):
    protocol_id: str
    generated_at: date
    total_required: int
    total_satisfied: int
    items: list[GapItem]

    @property
    def is_monitor_visit_ready(self) -> bool:
        blocking = {GapSeverity.MISSING, GapSeverity.EXPIRED, GapSeverity.OUTDATED_VERSION}
        return not any(item.severity in blocking for item in self.items)
