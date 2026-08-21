from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from trialready_api.core.security import AuthenticatedUser, get_current_user
from trialready_api.db.models import GapCheckRun, Protocol
from trialready_api.db.session import get_db_session
from trialready_api.schemas.gap_report import GapReport
from trialready_api.services.report_service import run_gap_check

router = APIRouter(prefix="/api/v1/protocols/{protocol_id}/gap-check", tags=["gap-checks"])


@router.post("", response_model=GapReport, status_code=status.HTTP_201_CREATED)
async def create_gap_check(
    protocol_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    user: AuthenticatedUser = Depends(get_current_user),
) -> GapReport:
    protocol = await db.get(Protocol, protocol_id)
    if protocol is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Protocol not found")

    return await run_gap_check(db, protocol_id=str(protocol_id), triggered_by=user.subject)


@router.get("/latest", response_model=GapReport)
async def get_latest_gap_check(
    protocol_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    user: AuthenticatedUser = Depends(get_current_user),
) -> GapReport:
    result = await db.execute(
        select(GapCheckRun)
        .where(GapCheckRun.protocol_id == protocol_id)
        .order_by(GapCheckRun.run_at.desc())
        .limit(1)
    )
    run = result.scalars().first()
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No gap check has been run yet")
    return GapReport.model_validate(run.report_json)
