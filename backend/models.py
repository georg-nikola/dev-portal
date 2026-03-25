import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, ForeignKey, String, Text, Enum, DateTime, JSON, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=True)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Service(Base):
    __tablename__ = "services"
    __table_args__ = (
        UniqueConstraint("owner_id", "name", name="uq_service_owner_name"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False, index=True)
    description = Column(Text)
    team = Column(String(100), index=True)
    status = Column(
        Enum("healthy", "degraded", "down", "unknown", name="service_status"),
        default="unknown",
        nullable=False,
    )
    status_url = Column(String(500))
    docs_url = Column(String(500))
    github_url = Column(String(500))
    dashboard_url = Column(String(500))
    tags = Column(JSON, default=list, nullable=False)
    cluster_id = Column(UUID(as_uuid=True), ForeignKey("clusters.id", ondelete="SET NULL"), nullable=True, index=True)
    last_checked_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)


class ClusterConfig(Base):
    __tablename__ = "clusters"
    __table_args__ = (
        UniqueConstraint("owner_id", "name", name="uq_cluster_owner_name"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    api_server_url = Column(String(500), nullable=True)
    encrypted_token = Column(Text, nullable=True)
    encrypted_kubeconfig = Column(Text, nullable=True)
    namespace_filter = Column(String(500), nullable=True)
    is_in_cluster = Column(Boolean, default=False, nullable=False)
    auto_discover = Column(Boolean, default=False, nullable=False)
    last_discovered_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
