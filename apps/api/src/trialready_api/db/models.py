"""SQLAlchemy 2.0 ORM models.

Design notes:
- UUID primary keys everywhere: safe to generate client-side, don't leak sequential
  volume, and merge cleanly if we ever shard by site/sponsor later.
- `audit_log_entries` is append-only by convention (enforced at the service layer,
  not the DB — a Postgres-level REVOKE UPDATE/DELETE is added in
  infra/bicep/modules/postgres.bicep's post-deploy script once real PHI is in play;
  see docs/compliance-checklist.md item "Immutable audit storage").
- `binder_documents.document_type_id` is a string reference into
  data/essential_documents.yaml rather than a DB-enforced FK. The checklist changes
  by protocol/sponsor over time and living in a versioned YAML file — reviewed like
  code — is more auditable than a mutable reference table for a compliance list.
"""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class Site(Base):
    __tablename__ = "sites"

    id: Mapped[uuid.UUID] = _uuid_pk()
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    principal_investigator_name: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_email: Mapped[str] = mapped_column(String(320), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    protocols: Mapped[list["Protocol"]] = relationship(back_populates="site")


class Protocol(Base):
    __tablename__ = "protocols"

    id: Mapped[uuid.UUID] = _uuid_pk()
    site_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sites.id"), nullable=False)
    sponsor_name: Mapped[str] = mapped_column(String(255), nullable=False)
    protocol_number: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    irb_approval_expiry_override: Mapped[date | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    site: Mapped["Site"] = relationship(back_populates="protocols")
    documents: Mapped[list["BinderDocument"]] = relationship(back_populates="protocol")
    gap_check_runs: Mapped[list["GapCheckRun"]] = relationship(back_populates="protocol")


class DocumentStatus(str, enum.Enum):
    PENDING_EXTRACTION = "pending_extraction"
    PENDING_HUMAN_REVIEW = "pending_human_review"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class BinderDocument(Base):
    __tablename__ = "binder_documents"

    id: Mapped[uuid.UUID] = _uuid_pk()
    protocol_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("protocols.id"), nullable=False)
    document_type_id: Mapped[str] = mapped_column(String(100), nullable=False)

    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    blob_path: Mapped[str] = mapped_column(String(1000), nullable=False)

    status: Mapped[DocumentStatus] = mapped_column(
        # values_callable is required: SQLAlchemy's Enum type sends the Python
        # enum member's .name ("PENDING_HUMAN_REVIEW") to the DB by default, but
        # the native Postgres enum created in the migration
        # (db/migrations/versions/0001_initial_schema.py) holds .value strings
        # ("pending_human_review") — without this, every insert/update fails
        # with "invalid input value for enum document_status".
        Enum(DocumentStatus, name="document_status", values_callable=lambda enum_cls: [e.value for e in enum_cls]),
        default=DocumentStatus.PENDING_EXTRACTION,
    )

    # Extracted / classification fields (populated by the classification agent)
    classification_confidence: Mapped[float | None] = mapped_column(Numeric(4, 3), nullable=True)
    extracted_effective_date: Mapped[date | None] = mapped_column(nullable=True)
    extracted_expiry_date: Mapped[date | None] = mapped_column(nullable=True)
    extracted_signer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    extracted_signed_date: Mapped[date | None] = mapped_column(nullable=True)
    version_label: Mapped[str | None] = mapped_column(String(50), nullable=True)

    superseded_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("binder_documents.id"), nullable=True
    )

    uploaded_by: Mapped[str] = mapped_column(String(255), nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    protocol: Mapped["Protocol"] = relationship(back_populates="documents")


class GapCheckRun(Base):
    __tablename__ = "gap_check_runs"

    id: Mapped[uuid.UUID] = _uuid_pk()
    protocol_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("protocols.id"), nullable=False)
    triggered_by: Mapped[str] = mapped_column(String(255), nullable=False)
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Full structured GapReport, stored verbatim for point-in-time reproducibility —
    # a monitor visit six weeks from now should see exactly what the site coordinator
    # saw when they ran the check, not a report re-computed against today's rules.
    report_json: Mapped[dict] = mapped_column(JSONB, nullable=False)

    protocol: Mapped["Protocol"] = relationship(back_populates="gap_check_runs")


class AuditLogEntry(Base):
    """Append-only. Never updated or deleted by application code."""

    __tablename__ = "audit_log_entries"

    id: Mapped[uuid.UUID] = _uuid_pk()
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    actor: Mapped[str] = mapped_column(String(255), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(100), nullable=False)
    details_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    request_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
