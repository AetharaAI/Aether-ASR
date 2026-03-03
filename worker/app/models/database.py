"""SQLAlchemy database models for worker (synchronous version)."""
from sqlalchemy import (
    Column, String, DateTime, Boolean, JSON, Integer, 
    Float, ForeignKey, Text, Enum
)
from sqlalchemy.dialects.postgresql import UUID, INET
from sqlalchemy.ext.declarative import declarative_base
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
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    api_key_id = Column(UUID(as_uuid=True), ForeignKey("api_keys.id", ondelete="SET NULL"))
    preset_id = Column(UUID(as_uuid=True), ForeignKey("presets.id", ondelete="SET NULL"))
    
    status = Column(Enum(JobStatusEnum), nullable=False, default=JobStatusEnum.PENDING)
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


class JobEvent(Base):
    __tablename__ = "job_events"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(String(32), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    event_type = Column(String(50), nullable=False)
    data = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


class UsageMetering(Base):
    __tablename__ = "usage_metering"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    api_key_id = Column(UUID(as_uuid=True), ForeignKey("api_keys.id", ondelete="SET NULL"))
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
