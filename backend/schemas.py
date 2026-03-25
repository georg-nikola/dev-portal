from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, HttpUrl, field_validator


ServiceStatus = str  # "healthy" | "degraded" | "down" | "unknown"

VALID_STATUSES = {"healthy", "degraded", "down", "unknown"}


class ServiceBase(BaseModel):
    name: str
    description: Optional[str] = None
    team: Optional[str] = None
    status: ServiceStatus = "unknown"
    status_url: Optional[str] = None
    docs_url: Optional[str] = None
    github_url: Optional[str] = None
    dashboard_url: Optional[str] = None
    tags: List[str] = []

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in VALID_STATUSES:
            raise ValueError(f"status must be one of: {', '.join(sorted(VALID_STATUSES))}")
        return v

    @field_validator("tags", mode="before")
    @classmethod
    def coerce_tags(cls, v):
        if v is None:
            return []
        return v


class ServiceCreate(ServiceBase):
    pass


class ServiceUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    team: Optional[str] = None
    status: Optional[ServiceStatus] = None
    status_url: Optional[str] = None
    docs_url: Optional[str] = None
    github_url: Optional[str] = None
    dashboard_url: Optional[str] = None
    tags: Optional[List[str]] = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_STATUSES:
            raise ValueError(f"status must be one of: {', '.join(sorted(VALID_STATUSES))}")
        return v

    @field_validator("tags", mode="before")
    @classmethod
    def coerce_tags(cls, v):
        if v is None:
            return None
        return v


class ServiceRead(ServiceBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    cluster_id: Optional[uuid.UUID] = None
    last_checked_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ServiceListResponse(BaseModel):
    items: List[ServiceRead]
    total: int


class HealthResponse(BaseModel):
    status: str
    version: str = "1.0.0"
