from __future__ import annotations

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone

from auth import get_current_user
from database import get_db
from models import Service, User
from schemas import ServiceCreate, ServiceRead, ServiceUpdate, ServiceListResponse
from status_checker import ping_url

router = APIRouter(prefix="/services", tags=["services"])


async def _get_owned_service(
    service_id: uuid.UUID, owner_id: uuid.UUID, db: AsyncSession,
) -> Service:
    result = await db.execute(
        select(Service).where(Service.id == service_id, Service.owner_id == owner_id)
    )
    service = result.scalar_one_or_none()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    return service


@router.get("", response_model=ServiceListResponse)
async def list_services(
    q: Optional[str] = Query(None, description="Search name/description/team"),
    team: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    tag: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = select(Service).where(Service.owner_id == current_user.id)

    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(
                Service.name.ilike(like),
                Service.description.ilike(like),
                Service.team.ilike(like),
            )
        )
    if team:
        stmt = stmt.where(Service.team == team)
    if status:
        stmt = stmt.where(Service.status == status)

    stmt = stmt.order_by(Service.name)

    result = await db.execute(stmt)
    services = result.scalars().all()

    # Filter by tag in Python (JSON array column — avoids DB-specific JSON operators)
    if tag:
        services = [s for s in services if tag in (s.tags or [])]

    return ServiceListResponse(items=services, total=len(services))


@router.get("/{service_id}", response_model=ServiceRead)
async def get_service(
    service_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await _get_owned_service(service_id, current_user.id, db)


@router.post("", response_model=ServiceRead, status_code=status.HTTP_201_CREATED)
async def create_service(
    payload: ServiceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    existing = await db.execute(
        select(Service).where(
            Service.owner_id == current_user.id, Service.name == payload.name,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Service '{payload.name}' already exists")

    service = Service(owner_id=current_user.id, **payload.model_dump())
    db.add(service)
    await db.commit()
    await db.refresh(service)
    return service


@router.put("/{service_id}", response_model=ServiceRead)
async def update_service(
    service_id: uuid.UUID,
    payload: ServiceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = await _get_owned_service(service_id, current_user.id, db)
    update_data = payload.model_dump(exclude_unset=True)

    if "name" in update_data and update_data["name"] != service.name:
        existing = await db.execute(
            select(Service).where(
                Service.owner_id == current_user.id,
                Service.name == update_data["name"],
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=409, detail=f"Service '{update_data['name']}' already exists"
            )

    for field, value in update_data.items():
        setattr(service, field, value)

    service.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(service)
    return service


@router.delete("/{service_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_service(
    service_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = await _get_owned_service(service_id, current_user.id, db)
    await db.delete(service)
    await db.commit()


@router.post("/{service_id}/check", response_model=ServiceRead)
async def trigger_status_check(
    service_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = await _get_owned_service(service_id, current_user.id, db)

    if not service.status_url:
        raise HTTPException(status_code=422, detail="Service has no status_url configured")

    new_status = await ping_url(service.status_url)
    service.status = new_status
    service.last_checked_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(service)
    return service
