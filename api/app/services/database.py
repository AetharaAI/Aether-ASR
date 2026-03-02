"""Database operations."""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select, update, and_
from typing import Optional, List, Tuple
from datetime import datetime, timedelta
import uuid

from app.config import settings
from app.models.database import Base, Tenant, APIKey, Job, JobEvent, Artifact, Preset


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
    """Initialize database tables and seed default data."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    async with async_session() as session:
        # Check if default tenant exists
        result = await session.execute(select(Tenant).where(Tenant.slug == 'default'))
        tenant = result.scalar_one_or_none()
        
        if not tenant:
            tenant_id = uuid.UUID('00000000-0000-0000-0000-000000000001')
            tenant = Tenant(
                id=tenant_id,
                name='Default Tenant',
                slug='default',
                config={
                    "default_model": "base",
                    "default_compute_type": "float16",
                    "max_file_size_mb": 500,
                    "max_duration_seconds": 7200,
                    "default_retention_days": 7,
                    "allowed_models": ["tiny", "base", "small", "medium", "large-v3"],
                    "features": {
                        "vad_enabled": True,
                        "diarization_enabled": False,
                        "word_timestamps": True
                    }
                },
                limits={
                    "requests_per_minute": 60,
                    "requests_per_hour": 1000,
                    "audio_seconds_per_day": 86400,
                    "concurrent_jobs": 5
                },
                is_active=True
            )
            session.add(tenant)
            
            # Create default API key
            api_key = APIKey(
                id=uuid.UUID('00000000-0000-0000-0000-000000000002'),
                tenant_id=tenant_id,
                key_hash='a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3',  # hash of '123'
                key_prefix='test-key',
                name='Default API Key',
                scopes='["transcription:read", "transcription:write"]',
                is_active=True
            )
            session.add(api_key)
            await session.commit()


async def check_database() -> bool:
    """Check database connectivity."""
    try:
        async with async_session() as session:
            result = await session.execute(select(1))
            return result.scalar() == 1
    except Exception:
        return False


# API Key operations
async def get_api_key_by_hash(key_hash: str) -> Optional[APIKey]:
    """Get API key by hash."""
    async with async_session() as session:
        result = await session.execute(
            select(APIKey).where(
                and_(
                    APIKey.key_hash == key_hash,
                    APIKey.is_active == True,
                    APIKey.is_revoked == False
                )
            )
        )
        return result.scalar_one_or_none()


# Job operations
async def create_job(
    job_id: str,
    tenant_id: uuid.UUID,
    api_key_id: Optional[uuid.UUID],
    config: dict,
    file_info: dict,
    webhook_url: Optional[str] = None,
    preset_id: Optional[uuid.UUID] = None
) -> Job:
    """Create a new job."""
    async with async_session() as session:
        retention_days = config.get("retention_days", 7)
        retention_until = datetime.utcnow() + timedelta(days=retention_days) if retention_days > 0 else None
        
        job = Job(
            id=job_id,
            tenant_id=tenant_id,
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
        await session.commit()
        await session.refresh(job)
        
        # Add job event
        event = JobEvent(
            job_id=job_id,
            event_type="created",
            data={"config": config, "file_info": file_info}
        )
        session.add(event)
        await session.commit()
        
        return job


async def get_job(job_id: str) -> Optional[Job]:
    """Get job by ID."""
    async with async_session() as session:
        result = await session.execute(
            select(Job).where(Job.id == job_id)
        )
        return result.scalar_one_or_none()


async def list_jobs(
    tenant_id: uuid.UUID,
    status: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    sort: str = "-created_at"
) -> Tuple[List[Job], int]:
    """List jobs with pagination."""
    async with async_session() as session:
        # Build query
        query = select(Job).where(Job.tenant_id == tenant_id)
        
        if status:
            query = query.where(Job.status == status)
        
        # Sort
        if sort.startswith("-"):
            sort_field = getattr(Job, sort[1:]).desc()
        else:
            sort_field = getattr(Job, sort).asc()
        query = query.order_by(sort_field)
        
        # Count total
        count_result = await session.execute(
            select(Job).where(Job.tenant_id == tenant_id)
        )
        total = len(count_result.scalars().all())
        
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
    """Update job status."""
    async with async_session() as session:
        job = await session.get(Job, job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")
        
        job.status = status
        
        if progress:
            job.progress.update(progress)
        
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
        
        await session.commit()
        await session.refresh(job)
        
        # Add event
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
    tenant_id: uuid.UUID,
    api_key_id: Optional[uuid.UUID],
    job_id: str,
    audio_seconds: float,
    audio_bytes: int,
    model: str,
    features: dict
):
    """Record usage for billing."""
    from app.models.database import UsageMetering
    
    async with async_session() as session:
        usage = UsageMetering(
            tenant_id=tenant_id,
            api_key_id=api_key_id,
            job_id=job_id,
            audio_seconds=audio_seconds,
            audio_bytes=audio_bytes,
            model=model,
            features=features
        )
        session.add(usage)
        await session.commit()
