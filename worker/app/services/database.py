"""Database operations for worker."""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
import os

from app.models.database import Base, Job, JobEvent, UsageMetering


# Database engine (synchronous for Celery)
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://asr:asr@postgres:5432/asr")
# Convert async URL to sync if needed
if DATABASE_URL.startswith("postgresql+asyncpg"):
    DATABASE_URL = DATABASE_URL.replace("postgresql+asyncpg", "postgresql")

engine = create_engine(
    DATABASE_URL,
    poolclass=NullPool,  # Celery workers use short-lived connections
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_job(job_id: str) -> Job:
    """Get job by ID."""
    with SessionLocal() as session:
        return session.query(Job).filter(Job.id == job_id).first()


def update_job_status(
    job_id: str,
    status: str,
    progress: dict = None,
    result: dict = None,
    error: dict = None
) -> Job:
    """Update job status."""
    from datetime import datetime
    
    with SessionLocal() as session:
        job = session.query(Job).filter(Job.id == job_id).first()
        if not job:
            raise ValueError(f"Job {job_id} not found")
        
        job.status = status
        
        if progress:
            current_progress = dict(job.progress) if job.progress else {}
            current_progress.update(progress)
            job.progress = current_progress
        
        if result:
            job.result = result
            job.completed_at = datetime.utcnow()
        
        if error:
            job.error = error
            job.failed_at = datetime.utcnow()
        
        if status == "processing" and not job.started_at:
            job.started_at = datetime.utcnow()
        
        if status == "cancelled":
            job.cancelled_at = datetime.utcnow()
        
        session.commit()
        
        # Add event
        event = JobEvent(
            job_id=job_id,
            event_type=status,
            data={"progress": progress, "result": result, "error": error}
        )
        session.add(event)
        session.commit()
        
        return job


def record_usage(
    tenant_id: str,
    api_key_id: str,
    job_id: str,
    audio_seconds: float,
    audio_bytes: int,
    model: str,
    features: dict
):
    """Record usage for billing."""
    from datetime import datetime
    
    with SessionLocal() as session:
        usage = UsageMetering(
            tenant_id=tenant_id,
            api_key_id=api_key_id,
            job_id=job_id,
            audio_seconds=audio_seconds,
            audio_bytes=audio_bytes,
            model=model,
            features=features,
            recorded_at=datetime.utcnow(),
            period_hour=datetime.utcnow().replace(minute=0, second=0, microsecond=0),
            period_day=datetime.utcnow().date(),
            period_month=datetime.utcnow().replace(day=1).date()
        )
        session.add(usage)
        session.commit()
