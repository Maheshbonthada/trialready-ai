"""Unit tests for the compliance decision layer.

These are the tests that matter most in this codebase — see
services/rules_engine.py's module docstring. Every branch of `_evaluate_one` is
exercised here with plain fixtures; nothing here touches a database, the network,
or an LLM.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from trialready_api.schemas.gap_report import BinderDocumentSnapshot, GapSeverity
from trialready_api.services.document_types import DocumentTypeSpec, ExpiryPolicy
from trialready_api.services.rules_engine import evaluate_binder

TODAY = date(2026, 8, 21)


def _spec(**overrides) -> DocumentTypeSpec:
    defaults = dict(
        id="test_doc",
        name="Test Document",
        category="test",
        required=True,
        expiry_policy=ExpiryPolicy.NONE,
        alert_window_days=30,
        regulatory_basis="Test basis",
    )
    defaults.update(overrides)
    return DocumentTypeSpec(**defaults)


def _doc(**overrides) -> BinderDocumentSnapshot:
    defaults = dict(
        id="doc-1",
        document_type_id="test_doc",
        status="accepted",
        classification_confidence=0.95,
        effective_date=TODAY - timedelta(days=10),
        expiry_date=None,
        version_label=None,
        uploaded_at=TODAY - timedelta(days=10),
    )
    defaults.update(overrides)
    return BinderDocumentSnapshot(**defaults)


class TestMissingDocuments:
    def test_flags_missing_when_no_document_uploaded(self):
        checklist = (_spec(),)
        report = evaluate_binder("proto-1", documents=[], as_of=TODAY, checklist=checklist)

        assert report.total_required == 1
        assert report.total_satisfied == 0
        assert len(report.items) == 1
        assert report.items[0].severity == GapSeverity.MISSING
        assert not report.is_monitor_visit_ready

    def test_rejected_document_still_counts_as_missing(self):
        checklist = (_spec(),)
        docs = [_doc(status="rejected")]
        report = evaluate_binder("proto-1", documents=docs, as_of=TODAY, checklist=checklist)

        assert report.items[0].severity == GapSeverity.MISSING


class TestPendingReview:
    def test_low_confidence_document_is_pending_review_not_satisfied(self):
        checklist = (_spec(),)
        docs = [_doc(status="pending_human_review")]
        report = evaluate_binder("proto-1", documents=docs, as_of=TODAY, checklist=checklist)

        assert report.total_satisfied == 0
        assert report.items[0].severity == GapSeverity.PENDING_REVIEW
        assert report.items[0].existing_document_id == "doc-1"

    def test_protocol_defined_expiry_missing_extracted_date_is_pending_review(self):
        checklist = (_spec(expiry_policy=ExpiryPolicy.PROTOCOL_DEFINED, alert_window_days=60),)
        docs = [_doc(status="accepted", expiry_date=None)]
        report = evaluate_binder("proto-1", documents=docs, as_of=TODAY, checklist=checklist)

        assert report.items[0].severity == GapSeverity.PENDING_REVIEW


class TestExpiry:
    def test_fixed_annual_expiry_computed_from_effective_date(self):
        checklist = (_spec(expiry_policy=ExpiryPolicy.FIXED_ANNUAL, expiry_days=365, alert_window_days=30),)
        docs = [_doc(effective_date=TODAY - timedelta(days=400), expiry_date=None)]
        report = evaluate_binder("proto-1", documents=docs, as_of=TODAY, checklist=checklist)

        assert report.items[0].severity == GapSeverity.EXPIRED

    def test_expiring_soon_within_alert_window(self):
        checklist = (_spec(expiry_policy=ExpiryPolicy.PROTOCOL_DEFINED, alert_window_days=60),)
        docs = [_doc(expiry_date=TODAY + timedelta(days=30))]
        report = evaluate_binder("proto-1", documents=docs, as_of=TODAY, checklist=checklist)

        assert report.items[0].severity == GapSeverity.EXPIRING_SOON
        assert report.items[0].due_date == TODAY + timedelta(days=30)

    def test_not_yet_in_alert_window_is_clean(self):
        checklist = (_spec(expiry_policy=ExpiryPolicy.PROTOCOL_DEFINED, alert_window_days=30),)
        docs = [_doc(expiry_date=TODAY + timedelta(days=90))]
        report = evaluate_binder("proto-1", documents=docs, as_of=TODAY, checklist=checklist)

        assert report.total_satisfied == 1
        assert report.items == []
        assert report.is_monitor_visit_ready

    def test_no_expiry_policy_never_expires(self):
        checklist = (_spec(expiry_policy=ExpiryPolicy.NONE),)
        docs = [_doc(expiry_date=None)]
        report = evaluate_binder("proto-1", documents=docs, as_of=TODAY + timedelta(days=3650), checklist=checklist)

        assert report.total_satisfied == 1

    def test_explicit_extracted_expiry_overrides_computed_policy_default(self):
        # Document itself states an earlier expiry than the policy default would compute.
        checklist = (_spec(expiry_policy=ExpiryPolicy.FIXED_ANNUAL, expiry_days=365, alert_window_days=10),)
        docs = [_doc(effective_date=TODAY - timedelta(days=10), expiry_date=TODAY - timedelta(days=1))]
        report = evaluate_binder("proto-1", documents=docs, as_of=TODAY, checklist=checklist)

        assert report.items[0].severity == GapSeverity.EXPIRED


class TestVersioning:
    def test_multiple_accepted_versions_flags_outdated(self):
        checklist = (_spec(version_sensitive=True),)
        docs = [
            _doc(id="old", effective_date=TODAY - timedelta(days=100)),
            _doc(id="new", effective_date=TODAY - timedelta(days=1)),
        ]
        report = evaluate_binder("proto-1", documents=docs, as_of=TODAY, checklist=checklist)

        assert report.items[0].severity == GapSeverity.OUTDATED_VERSION
        assert report.items[0].existing_document_id == "new"

    def test_single_accepted_version_is_clean(self):
        checklist = (_spec(version_sensitive=True),)
        docs = [_doc(id="only")]
        report = evaluate_binder("proto-1", documents=docs, as_of=TODAY, checklist=checklist)

        assert report.total_satisfied == 1


class TestGapReportSummary:
    def test_monitor_visit_ready_false_when_any_blocking_severity_present(self):
        checklist = (_spec(),)
        report = evaluate_binder("proto-1", documents=[], as_of=TODAY, checklist=checklist)
        assert report.is_monitor_visit_ready is False

    def test_monitor_visit_ready_true_with_no_gap_items(self):
        checklist = (_spec(),)
        docs = [_doc()]
        report = evaluate_binder("proto-1", documents=docs, as_of=TODAY, checklist=checklist)
        assert report.is_monitor_visit_ready is True

    @pytest.mark.parametrize("severity_field", ["total_required", "total_satisfied"])
    def test_counts_are_non_negative(self, severity_field):
        checklist = (_spec(),)
        report = evaluate_binder("proto-1", documents=[], as_of=TODAY, checklist=checklist)
        assert getattr(report, severity_field) >= 0
