from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from trialready_api.core.security import AuthenticatedUser, get_current_user
from trialready_api.db.models import Protocol, Site
from trialready_api.db.session import get_db_session
from trialready_api.schemas.api import ProtocolCreate, ProtocolOut, SiteCreate, SiteOut
from trialready_api.services import audit_service

router = APIRouter(prefix="/api/v1/sites", tags=["sites"])


@router.post("", response_model=SiteOut, status_code=status.HTTP_201_CREATED)
async def create_site(
    payload: SiteCreate,
    db: AsyncSession = Depends(get_db_session),
    user: AuthenticatedUser = Depends(get_current_user),
) -> Site:
    site = Site(
        name=payload.name,
        principal_investigator_name=payload.principal_investigator_name,
        contact_email=payload.contact_email,
    )
    db.add(site)
    await db.flush()
    await audit_service.record(
        db, actor=user.subject, action="site.created", entity_type="site", entity_id=str(site.id)
    )
    await db.commit()
    await db.refresh(site)
    return site


@router.get("", response_model=list[SiteOut])
async def list_sites(
    db: AsyncSession = Depends(get_db_session),
    user: AuthenticatedUser = Depends(get_current_user),
) -> list[Site]:
    # Unfiltered for the pilot — every coordinator sees every site. Fine at
    # pilot scale with one coordinator per site; becomes a real query
    # (filtered by the site_memberships table) once multi-coordinator sites
    # exist. See infra/bicep/modules/entra-b2c.md.
    result = await db.execute(select(Site).order_by(Site.created_at.desc()))
    return list(result.scalars().all())


@router.get("/{site_id}", response_model=SiteOut)
async def get_site(
    site_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    user: AuthenticatedUser = Depends(get_current_user),
) -> Site:
    site = await db.get(Site, site_id)
    if site is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")
    return site


@router.post("/{site_id}/protocols", response_model=ProtocolOut, status_code=status.HTTP_201_CREATED)
async def create_protocol(
    site_id: uuid.UUID,
    payload: ProtocolCreate,
    db: AsyncSession = Depends(get_db_session),
    user: AuthenticatedUser = Depends(get_current_user),
) -> Protocol:
    site = await db.get(Site, site_id)
    if site is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")

    protocol = Protocol(
        site_id=site_id,
        sponsor_name=payload.sponsor_name,
        protocol_number=payload.protocol_number,
        title=payload.title,
    )
    db.add(protocol)
    await db.flush()
    await audit_service.record(
        db, actor=user.subject, action="protocol.created", entity_type="protocol", entity_id=str(protocol.id)
    )
    await db.commit()
    await db.refresh(protocol)
    return protocol


@router.get("/{site_id}/protocols", response_model=list[ProtocolOut])
async def list_protocols_for_site(
    site_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    user: AuthenticatedUser = Depends(get_current_user),
) -> list[Protocol]:
    result = await db.execute(
        select(Protocol).where(Protocol.site_id == site_id).order_by(Protocol.created_at.desc())
    )
    return list(result.scalars().all())
