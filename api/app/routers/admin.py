"""Admin endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional

from app.services.auth import verify_admin


router = APIRouter()


@router.get("/stats")
async def get_stats(
    admin=Depends(verify_admin)
):
    """Get service statistics."""
    # This would query the database for actual stats
    return {
        "jobs": {
            "total": 0,
            "pending": 0,
            "processing": 0,
            "completed": 0,
            "failed": 0
        },
        "usage": {
            "audio_hours_processed": 0,
            "storage_bytes_used": 0
        },
        "tenants": {
            "total": 0,
            "active": 0
        }
    }


@router.get("/jobs/pending")
async def get_pending_jobs(
    limit: int = 100,
    admin=Depends(verify_admin)
):
    """Get pending jobs for monitoring."""
    return {
        "jobs": [],
        "count": 0
    }


@router.post("/jobs/{job_id}/retry")
async def retry_job(
    job_id: str,
    admin=Depends(verify_admin)
):
    """Retry a failed job."""
    return {
        "message": f"Job {job_id} queued for retry"
    }


@router.delete("/cache")
async def clear_cache(
    admin=Depends(verify_admin)
):
    """Clear Redis cache."""
    from app.services.cache import clear_all_cache
    await clear_all_cache()
    return {"message": "Cache cleared"}
