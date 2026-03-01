"""Redis cache operations."""
import redis.asyncio as redis
from typing import Optional, AsyncGenerator
import json

from app.config import settings


# Redis client
_redis_client: Optional[redis.Redis] = None


async def get_redis_client() -> redis.Redis:
    """Get or create Redis client."""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(
            settings.REDIS_URL,
            decode_responses=True
        )
    return _redis_client


async def check_redis() -> bool:
    """Check Redis connectivity."""
    try:
        client = await get_redis_client()
        return await client.ping()
    except Exception:
        return False


async def clear_all_cache():
    """Clear all cache."""
    client = await get_redis_client()
    await client.flushdb()


# Job event pub/sub
async def publish_job_event(job_id: str, event_type: str, data: dict):
    """Publish job event to Redis."""
    client = await get_redis_client()
    channel = f"job_events:{job_id}"
    message = json.dumps({"type": event_type, "data": data})
    await client.publish(channel, message)


async def subscribe_to_job_events(job_id: str) -> AsyncGenerator[dict, None]:
    """Subscribe to job events."""
    client = await get_redis_client()
    pubsub = client.pubsub()
    channel = f"job_events:{job_id}"
    await pubsub.subscribe(channel)
    
    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                data = json.loads(message["data"])
                yield data
    finally:
        await pubsub.unsubscribe(channel)


# Rate limiting helpers
async def check_rate_limit(key: str, limit: int, window_seconds: int) -> tuple[bool, int]:
    """Check if rate limit is exceeded."""
    client = await get_redis_client()
    
    current = await client.get(key)
    if current is None:
        # First request in window
        await client.setex(key, window_seconds, 1)
        return True, limit - 1
    
    current_count = int(current)
    if current_count >= limit:
        return False, 0
    
    await client.incr(key)
    return True, limit - current_count - 1
