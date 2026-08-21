"""Request/response DTOs for the HTTP layer — kept separate from the domain
schemas (schemas/gap_report.py) so a change to the wire format never forces a
change to the rules engine's inputs, and vice versa.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class SiteCreate(BaseModel):
    name: str
    principal_investigator_name: str
    contact_email: EmailStr


class SiteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    principal_investigator_name: str
    contact_email: str
    created_at: datetime


class ProtocolCreate(BaseModel):
    sponsor_name: str
    protocol_number: str
    title: str


class ProtocolOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    site_id: uuid.UUID
    sponsor_name: str
    protocol_number: str
    title: str
    created_at: datetime


class BinderDocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    document_type_id: str
    original_filename: str
    status: str
    classification_confidence: float | None
    extracted_effective_date: str | None = None
    extracted_expiry_date: str | None = None
    uploaded_at: datetime
