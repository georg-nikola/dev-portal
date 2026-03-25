import uuid
from datetime import datetime

from sqlalchemy import Column, String, Text, Enum, DateTime, JSON
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

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False, unique=True, index=True)
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
    last_checked_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
