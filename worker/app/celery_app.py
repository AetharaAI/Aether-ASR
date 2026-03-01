"""Celery application configuration."""
import os
from celery import Celery
from celery.signals import worker_ready, worker_shutdown

# Create Celery app
app = Celery("asr_worker")

# Configuration
app.conf.update(
    broker_url=os.getenv("CELERY_BROKER_URL", "redis://redis:6379/1"),
    result_backend=os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/2"),
    
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    
    # Task routing
    task_routes={
        "app.tasks.transcription.*": {"queue": "transcription"},
        "app.tasks.webhook.*": {"queue": "webhook"},
    },
    
    # Worker settings
    worker_prefetch_multiplier=1,  # Important for GPU tasks
    task_acks_late=True,  # Acknowledge after task completes
    task_reject_on_worker_lost=True,
    
    # Retries
    task_default_retry_delay=60,
    task_max_retries=3,
    
    # Results
    result_expires=3600,
    result_extended=True,
    
    # Monitoring
    worker_send_task_events=True,
    task_send_sent_event=True,
)

# Import tasks
app.autodiscover_tasks(["app.tasks.transcription", "app.tasks.webhook"])


@worker_ready.connect
def on_worker_ready(**kwargs):
    """Called when worker is ready."""
    print("Worker ready - warming up models...")
    
    try:
        from app.utils.gpu_manager import GPUPool
        GPUPool.warmup()
        print("Model warmup complete")
    except Exception as e:
        print(f"Model warmup failed: {e}")


@worker_shutdown.connect
def on_worker_shutdown(**kwargs):
    """Called when worker is shutting down."""
    print("Worker shutting down - cleaning up...")
    
    try:
        from app.utils.gpu_manager import GPUPool
        GPUPool.cleanup()
        print("Cleanup complete")
    except Exception as e:
        print(f"Cleanup failed: {e}")
