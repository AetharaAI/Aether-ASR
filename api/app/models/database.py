"""SQLAlchemy database models."""
from sqlalchemy import (
    Column, String, DateTime, Boolean, JSON, Integer, 
    Float, ForeignKey, Text, Enum as SQLEnum, create_engine
)
from sqlalchemy.dialects.postgresql import UUID, INET
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime
import enum


Base = declarative_base()


class JobStatusEnum(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class Job(Base):
    __tablename__ = "jobs"
    
    id = Column(String(32), primary_key=True)
    tenant_id = Column(String(255), nullable=False, index=True, default="open")
    api_key_id = Column(UUID(as_uuid=True), nullable=True)
    preset_id = Column(UUID(as_uuid=True), ForeignKey("presets.id", ondelete="SET NULL"))
    
    status = Column(SQLEnum(JobStatusEnum), nullable=False, default=JobStatusEnum.PENDING)
    config = Column(JSON, nullable=False, default=dict)
    file_info = Column(JSON, nullable=False, default=dict)
    progress = Column(JSON, nullable=False, default=dict)
    result = Column(JSON)
    error = Column(JSON)
    usage = Column(JSON)
    
    retention_until = Column(DateTime(timezone=True))
    webhook_url = Column(String(2048))
    webhook_delivered_at = Column(DateTime(timezone=True))
    webhook_attempts = Column(Integer, default=0)
    
    client_ip = Column(INET)
    user_agent = Column(Text)
    
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    failed_at = Column(DateTime(timezone=True))
    cancelled_at = Column(DateTime(timezone=True))
    expires_at = Column(DateTime(timezone=True))
    
    preset = relationship("Preset", back_populates="jobs")
    events = relationship("JobEvent", back_populates="job")
    artifacts = relationship("Artifact", back_populates="job")


class JobEvent(Base):
    __tablename__ = "job_events"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(String(32), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    event_type = Column(String(50), nullable=False)
    data = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    
    job = relationship("Job", back_populates="events")


class Artifact(Base):
    __tablename__ = "artifacts"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(String(32), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    type = Column(String(50), nullable=False)
    format = Column(String(10), nullable=False)
    storage_path = Column(String(1024), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    checksum = Column(String(64))
    artifact_metadata = Column(JSON, default=dict)
    download_count = Column(Integer, default=0)
    last_downloaded_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    expires_at = Column(DateTime(timezone=True))
    
    job = relationship("Job", back_populates="artifacts")


class Preset(Base):
    __tablename__ = "presets"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String(255), nullable=False, index=True, default="open")
    name = Column(String(255), nullable=False)
    description = Column(Text)
    config = Column(JSON, nullable=False)
    is_default = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    
    jobs = relationship("Job", back_populates="preset")


class UsageMetering(Base):
    __tablename__ = "usage_metering"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String(255), nullable=False, index=True, default="open")
    job_id = Column(String(32), ForeignKey("jobs.id", ondelete="SET NULL"))
    
    audio_seconds = Column(Float, nullable=False)
    audio_bytes = Column(Integer, nullable=False)
    model = Column(String(50), nullable=False)
    features = Column(JSON, nullable=False, default=dict)
    cost_estimate = Column(Float)
    cost_currency = Column(String(3), default="USD")
    
    recorded_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    period_hour = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    period_day = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    period_month = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    
    region = Column(String(50))
    worker_id = Column(String(100))


class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String(255), index=True, default="open")
    job_id = Column(String(32), ForeignKey("jobs.id", ondelete="SET NULL"))
    
    action = Column(String(50), nullable=False)
    resource_type = Column(String(50), nullable=False)
    resource_id = Column(String(255))
    details = Column(JSON, nullable=False, default=dict)
    
    ip_address = Column(INET)
    user_agent = Column(Text)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
