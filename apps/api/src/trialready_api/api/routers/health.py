"""Liveness/readiness probes for Azure Container Apps.

Split deliberately: liveness never touches the database (a slow DB should trigger
alerting, not a container restart loop that makes the outage worse); readiness
does, and is what should gate traffic during rollout and hold Container Apps'
revision traffic-split back until the new revision can actually serve requests.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from trialready_api.db.session import get_db_session

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def liveness() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz")
async def readiness(db: AsyncSession = Depends(get_db_session)) -> dict[str, str]:
    try:
        await db.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 — readiness probe must never leak internals
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="not ready") from exc
    return {"status": "ready"}
