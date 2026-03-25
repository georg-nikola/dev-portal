from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import get_current_user
from database import get_db
from discovery import build_k8s_client, discover_workloads, sync_discovered_services
from encryption import encrypt_value
from models import ClusterConfig, User
from schemas_cluster import (
    ClusterConfigCreate,
    ClusterConfigListResponse,
    ClusterConfigRead,
    ClusterConfigUpdate,
    DiscoveryResult,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/clusters", tags=["clusters"])


def _to_read(cluster: ClusterConfig) -> ClusterConfigRead:
    """Convert a ClusterConfig ORM object to a read schema (never expose credentials)."""
    return ClusterConfigRead(
        id=cluster.id,
        owner_id=cluster.owner_id,
        name=cluster.name,
        api_server_url=cluster.api_server_url,
        namespace_filter=cluster.namespace_filter,
        is_in_cluster=cluster.is_in_cluster,
        auto_discover=cluster.auto_discover,
        has_token=cluster.encrypted_token is not None,
        has_kubeconfig=cluster.encrypted_kubeconfig is not None,
        last_discovered_at=cluster.last_discovered_at,
        created_at=cluster.created_at,
        updated_at=cluster.updated_at,
    )


async def _get_owned_cluster(
    cluster_id: uuid.UUID, owner_id: uuid.UUID, db: AsyncSession,
) -> ClusterConfig:
    result = await db.execute(
        select(ClusterConfig).where(
            ClusterConfig.id == cluster_id, ClusterConfig.owner_id == owner_id,
        )
    )
    cluster = result.scalar_one_or_none()
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")
    return cluster


@router.get("", response_model=ClusterConfigListResponse)
async def list_clusters(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(ClusterConfig)
        .where(ClusterConfig.owner_id == current_user.id)
        .order_by(ClusterConfig.name)
    )
    clusters = result.scalars().all()
    return ClusterConfigListResponse(
        items=[_to_read(c) for c in clusters],
        total=len(clusters),
    )


@router.get("/{cluster_id}", response_model=ClusterConfigRead)
async def get_cluster(
    cluster_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cluster = await _get_owned_cluster(cluster_id, current_user.id, db)
    return _to_read(cluster)


@router.post("", response_model=ClusterConfigRead, status_code=status.HTTP_201_CREATED)
async def create_cluster(
    payload: ClusterConfigCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    existing = await db.execute(
        select(ClusterConfig).where(
            ClusterConfig.owner_id == current_user.id,
            ClusterConfig.name == payload.name,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Cluster '{payload.name}' already exists")

    cluster = ClusterConfig(
        owner_id=current_user.id,
        name=payload.name,
        api_server_url=payload.api_server_url,
        encrypted_token=encrypt_value(payload.token) if payload.token else None,
        encrypted_kubeconfig=encrypt_value(payload.kubeconfig) if payload.kubeconfig else None,
        namespace_filter=payload.namespace_filter,
        is_in_cluster=payload.is_in_cluster,
        auto_discover=payload.auto_discover,
    )
    db.add(cluster)
    await db.commit()
    await db.refresh(cluster)
    return _to_read(cluster)


@router.put("/{cluster_id}", response_model=ClusterConfigRead)
async def update_cluster(
    cluster_id: uuid.UUID,
    payload: ClusterConfigUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cluster = await _get_owned_cluster(cluster_id, current_user.id, db)
    update_data = payload.model_dump(exclude_unset=True)

    if "name" in update_data and update_data["name"] != cluster.name:
        existing = await db.execute(
            select(ClusterConfig).where(
                ClusterConfig.owner_id == current_user.id,
                ClusterConfig.name == update_data["name"],
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=409, detail=f"Cluster '{update_data['name']}' already exists"
            )

    # Handle credential fields specially — encrypt before storage
    if "token" in update_data:
        token = update_data.pop("token")
        cluster.encrypted_token = encrypt_value(token) if token else None
    if "kubeconfig" in update_data:
        kubeconfig = update_data.pop("kubeconfig")
        cluster.encrypted_kubeconfig = encrypt_value(kubeconfig) if kubeconfig else None

    for field, value in update_data.items():
        setattr(cluster, field, value)

    cluster.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(cluster)
    return _to_read(cluster)


@router.delete("/{cluster_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cluster(
    cluster_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cluster = await _get_owned_cluster(cluster_id, current_user.id, db)
    await db.delete(cluster)
    await db.commit()


@router.post("/{cluster_id}/discover", response_model=DiscoveryResult)
async def trigger_discovery(
    cluster_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cluster = await _get_owned_cluster(cluster_id, current_user.id, db)

    try:
        api_client = await build_k8s_client(cluster)
        workloads = await discover_workloads(api_client, cluster.namespace_filter)
    except Exception as exc:
        logger.exception("Discovery failed for cluster %s: %s", cluster.name, exc)
        raise HTTPException(
            status_code=502,
            detail=f"Failed to connect to cluster: {exc}",
        )

    result = await sync_discovered_services(
        db=db,
        owner_id=current_user.id,
        cluster_id=cluster.id,
        cluster_name=cluster.name,
        workloads=workloads,
    )

    cluster.last_discovered_at = datetime.now(timezone.utc)
    await db.commit()

    return result
