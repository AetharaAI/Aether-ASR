"""Health check endpoints."""
from fastapi import APIRouter, Depends
from datetime import datetime
import asyncio

from app.config import settings
from app.services.database import check_database
from app.services.cache import check_redis
from app.services.storage import check_storage


router = APIRouter()


@router.get("/api/health", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    services = {}
    overall_status = "healthy"
    
    # Check database
    try:
        db_healthy = await check_database()
        services["database"] = "connected" if db_healthy else "error"
        if not db_healthy:
            overall_status = "degraded"
    except Exception as e:
        services["database"] = f"error: {str(e)}"
        overall_status = "degraded"
    
    # Check Redis
    try:
        redis_healthy = await check_redis()
        services["redis"] = "connected" if redis_healthy else "error"
        if not redis_healthy:
            overall_status = "degraded"
    except Exception as e:
        services["redis"] = f"error: {str(e)}"
        overall_status = "degraded"
    
    # Check storage
    try:
        storage_healthy = await check_storage()
        services["storage"] = "connected" if storage_healthy else "error"
        if not storage_healthy:
            overall_status = "degraded"
    except Exception as e:
        services["storage"] = f"error: {str(e)}"
        overall_status = "degraded"
    
    # Check GPU (optional)
    try:
        import torch
        if torch.cuda.is_available():
            gpu_count = torch.cuda.device_count()
            gpu_name = torch.cuda.get_device_name(0) if gpu_count > 0 else None
            services["gpu"] = {
                "available": True,
                "count": gpu_count,
                "name": gpu_name
            }
        else:
            services["gpu"] = {"available": False}
    except ImportError:
        services["gpu"] = {"available": False, "reason": "torch not installed"}
    
    return {
        "status": overall_status,
        "version": settings.APP_VERSION,
        "timestamp": datetime.utcnow().isoformat(),
        "services": services
    }


@router.get("/api/metrics", tags=["Health"])
async def metrics():
    """Prometheus metrics endpoint."""
    # This would typically use prometheus_client
    # For now, return basic metrics
    return {
        "jobs_total": 0,
        "jobs_completed": 0,
        "jobs_failed": 0,
        "audio_processed_seconds": 0
    }


@router.get("/api/version", tags=["Health"])
async def version():
    """API version information."""
    return {
        "version": settings.APP_VERSION,
        "api_version": "v1",
        "whisper_version": "20231117",
        "build": {
            "commit": "unknown",
            "branch": "main",
            "timestamp": datetime.utcnow().isoformat()
        }
    }
