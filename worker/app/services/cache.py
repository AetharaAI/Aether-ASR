"""Redis cache operations for worker."""
import redis
import json
import os


# Redis client
_redis_client = None


def get_redis_client():
    """Get or create Redis client."""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(
            os.getenv("REDIS_URL", "redis://redis:6379/0"),
            decode_responses=True
        )
    return _redis_client


def publish_job_event(job_id: str, event_type: str, data: dict):
    """Publish job event to Redis."""
    try:
        client = get_redis_client()
        channel = f"job_events:{job_id}"
        message = json.dumps({"type": event_type, "data": data})
        client.publish(channel, message)
    except Exception:
        # Don't fail if Redis is unavailable
        pass
