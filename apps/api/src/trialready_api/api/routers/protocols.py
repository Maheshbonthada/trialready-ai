from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from trialready_api.core.security import AuthenticatedUser, get_current_user
from trialready_api.db.models import Protocol
from trialready_api.db.session import get_db_session
from trialready_api.schemas.api import ProtocolOut

router = APIRouter(prefix="/api/v1/protocols", tags=["protocols"])


@router.get("/{protocol_id}", response_model=ProtocolOut)
async def get_protocol(
    protocol_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    user: AuthenticatedUser = Depends(get_current_user),
) -> Protocol:
    protocol = await db.get(Protocol, protocol_id)
    if protocol is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Protocol not found")
    return protocol
