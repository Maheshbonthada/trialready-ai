"""Append-only audit logging.

Every state-changing action in the system — a document accepted or sent to human
review, a gap-check run, a manual override — is recorded here with who, what, and
why. This exists from day one even though the MVP only runs on synthetic data,
because audit trails cannot be retrofitted onto a system after the fact: the
capability has to be architected in before it's ever needed for real. See
docs/compliance-checklist.md.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from trialready_api.db.models import AuditLogEntry


async def record(
    db: AsyncSession,
    *,
    actor: str,
    action: str,
    entity_type: str,
    entity_id: str,
    details: dict | None = None,
    request_id: str | None = None,
) -> None:
    entry = AuditLogEntry(
        actor=actor,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details_json=details or {},
        request_id=request_id,
    )
    db.add(entry)
    # Deliberately no commit here — callers batch this into the same transaction as
    # the business-logic write it's documenting, so an audit entry can never exist
    # for a write that didn't happen, or vice versa.
