"""End-to-end test of ingest -> classify -> gap-check, against a real Postgres,
using fake OCR/classifier/blob-store implementations (no network, no Azure).
Run with `docker compose up -d postgres` locally, then `pytest -m ""` from
apps/api, or via `.github/workflows/ci.yml`'s postgres service container.
"""

from __future__ import annotations

from datetime import date

import pytest

from trialready_api.agents.classification_agent import ClassificationResult, FakeDocumentClassifier
from trialready_api.agents.ocr_client import FakeDocumentOcrClient
from trialready_api.config import Settings
from trialready_api.db.models import Protocol, Site
from trialready_api.schemas.gap_report import GapSeverity
from trialready_api.services.blob_storage import InMemoryBlobStore
from trialready_api.services.document_ingestion import ingest_document
from trialready_api.services.report_service import run_gap_check


@pytest.fixture
def settings() -> Settings:
    return Settings(classification_min_confidence=0.85)


async def _make_protocol(db_session) -> Protocol:
    site = Site(name="Riverside Research", principal_investigator_name="Dr. A. Okafor", contact_email="a@example.com")
    db_session.add(site)
    await db_session.flush()

    protocol = Protocol(site_id=site.id, sponsor_name="Acme Pharma", protocol_number="ACM-204", title="A Study")
    db_session.add(protocol)
    await db_session.flush()
    return protocol


async def test_high_confidence_document_is_accepted_and_clears_the_gap(db_session, settings):
    protocol = await _make_protocol(db_session)

    classifier = FakeDocumentClassifier(
        results=[
            ClassificationResult(
                document_type_id="financial_disclosure_form",
                confidence=0.97,
                effective_date=date(2026, 1, 1),
                rationale="Matches financial disclosure form template",
            )
        ]
    )

    doc = await ingest_document(
        db=db_session,
        protocol_id=str(protocol.id),
        file_bytes=b"%PDF-1.4 fake",
        original_filename="findisc.pdf",
        content_type="application/pdf",
        uploaded_by="coordinator@example.com",
        settings=settings,
        ocr_client=FakeDocumentOcrClient(),
        classifier=classifier,
        blob_store=InMemoryBlobStore(),
    )

    assert doc.status.value == "accepted"

    report = await run_gap_check(db_session, protocol_id=str(protocol.id), triggered_by="coordinator@example.com")
    matching_items = [i for i in report.items if i.document_type_id == "financial_disclosure_form"]
    assert matching_items == []  # no gap item at all: fully satisfied


async def test_low_confidence_document_is_pending_review_not_satisfied(db_session, settings):
    protocol = await _make_protocol(db_session)

    classifier = FakeDocumentClassifier(
        results=[
            ClassificationResult(
                document_type_id="financial_disclosure_form",
                confidence=0.40,
                rationale="Blurry scan, low confidence",
            )
        ]
    )

    await ingest_document(
        db=db_session,
        protocol_id=str(protocol.id),
        file_bytes=b"%PDF-1.4 fake",
        original_filename="findisc-blurry.pdf",
        content_type="application/pdf",
        uploaded_by="coordinator@example.com",
        settings=settings,
        ocr_client=FakeDocumentOcrClient(),
        classifier=classifier,
        blob_store=InMemoryBlobStore(),
    )

    report = await run_gap_check(db_session, protocol_id=str(protocol.id), triggered_by="coordinator@example.com")
    item = next(i for i in report.items if i.document_type_id == "financial_disclosure_form")
    assert item.severity == GapSeverity.PENDING_REVIEW
    assert report.is_monitor_visit_ready is False


async def test_unrecognized_document_does_not_silently_satisfy_any_requirement(db_session, settings):
    protocol = await _make_protocol(db_session)

    classifier = FakeDocumentClassifier(
        results=[ClassificationResult(document_type_id=None, confidence=0.0, rationale="No match found")]
    )

    doc = await ingest_document(
        db=db_session,
        protocol_id=str(protocol.id),
        file_bytes=b"%PDF-1.4 fake",
        original_filename="mystery.pdf",
        content_type="application/pdf",
        uploaded_by="coordinator@example.com",
        settings=settings,
        ocr_client=FakeDocumentOcrClient(),
        classifier=classifier,
        blob_store=InMemoryBlobStore(),
    )

    assert doc.status.value == "pending_human_review"
    assert doc.document_type_id == "unclassified"
