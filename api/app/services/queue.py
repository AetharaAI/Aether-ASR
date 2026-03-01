"""Celery queue operations."""
from celery import Celery
from typing import Optional

from app.config import settings


# Celery app
celery_app = Celery("asr_tasks")

celery_app.conf.update(
    broker_url=settings.CELERY_BROKER_URL,
    result_backend=settings.CELERY_RESULT_BACKEND,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_routes={
        "tasks.transcription.*": {"queue": "transcription"},
        "tasks.webhook.*": {"queue": "webhook"},
    },
    task_default_retry_delay=60,
    task_max_retries=3,
    result_expires=3600,
)


async def enqueue_job(job_id: str, storage_key: str, config: dict):
    """Enqueue a transcription job."""
    celery_app.send_task(
        "tasks.transcription.transcribe_audio",
        args=[job_id, storage_key, config],
        queue="transcription"
    )


async def cancel_job(job_id: str) -> bool:
    """Cancel a pending job."""
    # Revoke the task if it's still pending
    from celery.result import AsyncResult
    
    # This would require storing the task ID when enqueuing
    # For now, placeholder
    return True


async def get_job_status(job_id: str) -> Optional[dict]:
    """Get job status from Celery."""
    from celery.result import AsyncResult
    
    # This would require storing the task ID
    # For now, placeholder
    return None


async def send_webhook(job_id: str, webhook_url: str, result: dict):
    """Send webhook notification."""
    celery_app.send_task(
        "tasks.webhook.send_webhook",
        args=[job_id, webhook_url, result],
        queue="webhook"
    )
