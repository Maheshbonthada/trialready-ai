from __future__ import annotations

from trialready_api.services.document_types import load_checklist, required_document_types


def test_checklist_loads_and_ids_are_unique():
    checklist = load_checklist()
    ids = [spec.id for spec in checklist]
    assert len(ids) == len(set(ids)), "duplicate document_type_id in essential_documents.yaml"
    assert len(checklist) > 0


def test_all_loaded_entries_are_currently_required():
    # documented assumption: everything in the MVP checklist is required=true;
    # this test exists so an editor adding an optional entry notices the
    # rules-engine/report totals assumption it would break.
    assert all(spec.required for spec in required_document_types())


def test_fixed_annual_entries_declare_expiry_days():
    from trialready_api.services.document_types import ExpiryPolicy

    for spec in load_checklist():
        if spec.expiry_policy in (ExpiryPolicy.FIXED_ANNUAL, ExpiryPolicy.CUSTOM_DAYS):
            assert spec.expiry_days is not None, f"{spec.id} declares {spec.expiry_policy} without expiry_days"
