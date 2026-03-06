"""Database operations."""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select, update, and_
from sqlalchemy.orm import flag_modified
from typing import Optional, List, Tuple
from datetime import datetime, timedelta
import uuid

from app.config import settings
from app.models.database import Base, Job, JobEvent, Artifact, Preset


# Database engine
engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=20,
    echo=settings.DEBUG
)

# Session factory
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db():
    """Initialize database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def check_database() -> bool:
    """Check database connectivity."""
    try:
        async with async_session() as session:
            result = await session.execute(select(1))
            return result.scalar() == 1
    except Exception:
        return False


# Job operations
async def create_job(
    job_id: str,
    tenant_id: str,
    api_key_id: Optional[str],
    config: dict,
    file_info: dict,
    webhook_url: Optional[str] = None,
    preset_id: Optional[uuid.UUID] = None
) -> Job:
    """Create a new job and its initial event in a single session."""
    async with async_session() as session:
        retention_days = config.get("retention_days", 7)
        retention_until = (
            datetime.utcnow() + timedelta(days=retention_days)
            if retention_days > 0 else None
        )

        job = Job(
            id=job_id,
            tenant_id=tenant_id or "open",
            api_key_id=api_key_id,
            preset_id=preset_id,
            config=config,
            file_info=file_info,
            webhook_url=webhook_url,
            retention_until=retention_until,
            progress={
                "percent": 0,
                "current_step": "queued",
                "steps_total": 5,
                "chunks_processed": 0,
                "chunks_total": 0,
                "message": "Waiting in queue"
            }
        )
        session.add(job)

        # Add initial event in the same transaction so we don't get
        # detached-instance errors from a second session open.
        event = JobEvent(
            job_id=job_id,
            event_type="created",
            data={"config": config, "file_info": file_info}
        )
        session.add(event)

        await session.commit()
        await session.refresh(job)

        return job


async def get_job(job_id: str) -> Optional[Job]:
    """Get job by ID."""
    async with async_session() as session:
        result = await session.execute(
            select(Job).where(Job.id == job_id)
        )
        return result.scalar_one_or_none()


async def list_jobs(
    tenant_id: str = "open",
    status: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    sort: str = "-created_at"
) -> Tuple[List[Job], int]:
    """List jobs with pagination."""
    async with async_session() as session:
        # Build query
        query = select(Job)

        if status:
            query = query.where(Job.status == status)

        # Sort
        if sort.startswith("-"):
            sort_field = getattr(Job, sort[1:]).desc()
        else:
            sort_field = getattr(Job, sort).asc()
        query = query.order_by(sort_field)

        # Count total (efficient approach)
        from sqlalchemy import func
        count_query = select(func.count()).select_from(Job)
        if status:
            count_query = count_query.where(Job.status == status)
        count_result = await session.execute(count_query)
        total = count_result.scalar()

        # Paginate
        query = query.offset(offset).limit(limit)
        result = await session.execute(query)
        jobs = result.scalars().all()

        return jobs, total


async def update_job_status(
    job_id: str,
    status: str,
    progress: Optional[dict] = None,
    result: Optional[dict] = None,
    error: Optional[dict] = None
) -> Job:
    """Update job status with proper JSON mutation tracking."""
    async with async_session() as session:
        job = await session.get(Job, job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        job.status = status

        if progress:
            # Merge progress dict (don't replace entirely)
            current_progress = dict(job.progress or {})
            current_progress.update(progress)
            job.progress = current_progress
            # Tell SQLAlchemy the JSON column was mutated
            flag_modified(job, "progress")

        if result:
            job.result = result
            flag_modified(job, "result")
            job.completed_at = datetime.utcnow()

        if error:
            job.error = error
            flag_modified(job, "error")
            job.failed_at = datetime.utcnow()

        if status == "processing" and not job.started_at:
            job.started_at = datetime.utcnow()

        if status == "cancelled":
            job.cancelled_at = datetime.utcnow()

        await session.commit()
        await session.refresh(job)

        # Add event in the same session
        event = JobEvent(
            job_id=job_id,
            event_type=status,
            data={"progress": progress, "result": result, "error": error}
        )
        session.add(event)
        await session.commit()

        return job


async def get_job_artifacts(job_id: str) -> List[Artifact]:
    """Get artifacts for a job."""
    async with async_session() as session:
        result = await session.execute(
            select(Artifact).where(Artifact.job_id == job_id)
        )
        return result.scalars().all()


async def record_usage(
    tenant_id: str = "open",
    api_key_id: Optional[str] = None,
    job_id: str = "",
    audio_seconds: float = 0,
    audio_bytes: int = 0,
    model: str = "",
    features: dict = {}
):
    """Record usage for metering."""
    from app.models.database import UsageMetering

    async with async_session() as session:
        usage = UsageMetering(
            tenant_id=tenant_id or "open",
            job_id=job_id,
            audio_seconds=audio_seconds,
            audio_bytes=audio_bytes,
            model=model,
            features=features
        )
        session.add(usage)
        await session.commit()
