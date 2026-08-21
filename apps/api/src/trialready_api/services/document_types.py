"""Loads the canonical Site Regulatory Binder checklist.

The checklist is a reviewed, versioned YAML file (data/essential_documents.yaml),
not a database table an admin can silently edit through a UI. Compliance-critical
"what counts as required" logic should go through the same code review as
everything else — that's the whole point of treating it as config-as-code.
"""

from __future__ import annotations

import os
from enum import Enum
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel

_DEFAULT_PATH = Path(__file__).resolve().parents[5] / "data" / "essential_documents.yaml"


class ExpiryPolicy(str, Enum):
    NONE = "none"
    FIXED_ANNUAL = "fixed_annual"
    PROTOCOL_DEFINED = "protocol_defined"
    CUSTOM_DAYS = "custom_days"


class DocumentTypeSpec(BaseModel):
    id: str
    name: str
    category: str
    required: bool = True
    expiry_policy: ExpiryPolicy
    expiry_days: int | None = None
    alert_window_days: int = 30
    regulatory_basis: str = ""
    version_sensitive: bool = False
    living_document: bool = False


def _checklist_path() -> Path:
    override = os.environ.get("TRIALREADY_CHECKLIST_PATH")
    return Path(override) if override else _DEFAULT_PATH


@lru_cache
def load_checklist() -> tuple[DocumentTypeSpec, ...]:
    path = _checklist_path()
    with path.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    return tuple(DocumentTypeSpec.model_validate(entry) for entry in raw)


def required_document_types() -> tuple[DocumentTypeSpec, ...]:
    return tuple(spec for spec in load_checklist() if spec.required)


def get_document_type(document_type_id: str) -> DocumentTypeSpec | None:
    return next((spec for spec in load_checklist() if spec.id == document_type_id), None)
