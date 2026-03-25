from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, field_validator, model_validator


class ClusterConfigCreate(BaseModel):
    name: str
    api_server_url: Optional[str] = None
    token: Optional[str] = None
    kubeconfig: Optional[str] = None
    namespace_filter: Optional[str] = None
    is_in_cluster: bool = False
    auto_discover: bool = False

    @field_validator("name")
    @classmethod
    def name_min_length(cls, v: str) -> str:
        if len(v.strip()) < 2:
            raise ValueError("Cluster name must be at least 2 characters")
        return v.strip()

    @model_validator(mode="after")
    def validate_auth(self):
        if not self.is_in_cluster:
            if not self.token and not self.kubeconfig:
                raise ValueError(
                    "Either token or kubeconfig is required when not using in-cluster config"
                )
            if not self.api_server_url:
                raise ValueError(
                    "api_server_url is required when not using in-cluster config"
                )
        return self


class ClusterConfigUpdate(BaseModel):
    name: Optional[str] = None
    api_server_url: Optional[str] = None
    token: Optional[str] = None
    kubeconfig: Optional[str] = None
    namespace_filter: Optional[str] = None
    is_in_cluster: Optional[bool] = None
    auto_discover: Optional[bool] = None


class ClusterConfigRead(BaseModel):
    id: uuid.UUID
    owner_id: uuid.UUID
    name: str
    api_server_url: Optional[str] = None
    namespace_filter: Optional[str] = None
    is_in_cluster: bool
    auto_discover: bool
    has_token: bool
    has_kubeconfig: bool
    last_discovered_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ClusterConfigListResponse(BaseModel):
    items: List[ClusterConfigRead]
    total: int


class DiscoveredWorkload(BaseModel):
    name: str
    namespace: str
    kind: str
    status: str
    replicas_ready: int
    replicas_desired: int
    labels: dict
    health_check_url: Optional[str] = None


class DiscoveryResultItem(BaseModel):
    name: str
    action: str  # "created" | "updated" | "unchanged"


class DiscoveryResult(BaseModel):
    cluster_name: str
    total_workloads: int
    created: int
    updated: int
    unchanged: int
    items: List[DiscoveryResultItem]
