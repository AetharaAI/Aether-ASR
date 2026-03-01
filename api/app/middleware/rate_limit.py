"""Rate limiting middleware using Redis."""
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
import time

from app.services.cache import get_redis_client
from app.config import settings


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting with sliding window algorithm."""
    
    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for health checks and docs
        if request.url.path in ["/api/health", "/api/version", "/docs", "/redoc", "/openapi.json"]:
            return await call_next(request)
        
        # Get API key from header
        api_key = request.headers.get(settings.API_KEY_HEADER)
        if not api_key:
            # No API key - use IP-based rate limiting
            api_key = f"ip:{request.client.host}" if request.client else "ip:unknown"
        
        # Check rate limit
        redis = await get_redis_client()
        
        # Sliding window: requests per minute
        minute_key = f"rate_limit:{api_key}:minute"
        minute_count = await redis.get(minute_key)
        
        if minute_count and int(minute_count) >= settings.RATE_LIMIT_REQUESTS_PER_MINUTE:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                headers={
                    "X-RateLimit-Limit": str(settings.RATE_LIMIT_REQUESTS_PER_MINUTE),
                    "X-RateLimit-Remaining": "0",
                    "Retry-After": "60"
                },
                detail={
                    "error": {
                        "code": "RATE_LIMIT_EXCEEDED",
                        "message": "Rate limit exceeded. Try again later."
                    }
                }
            )
        
        # Increment counters
        pipe = redis.pipeline()
        pipe.incr(minute_key)
        pipe.expire(minute_key, 60)
        await pipe.execute()
        
        # Get current count for headers
        current_count = int(await redis.get(minute_key) or 0)
        remaining = max(0, settings.RATE_LIMIT_REQUESTS_PER_MINUTE - current_count)
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(settings.RATE_LIMIT_REQUESTS_PER_MINUTE)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        
        return response
