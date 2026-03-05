"""FastAPI main application."""
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from contextlib import asynccontextmanager
import time
import structlog

from app.config import settings
from app.routers import openai, transcriptions, models, health, admin, websocket, account, tts
from app.middleware.logging import LoggingMiddleware
from app.middleware.rate_limit import RateLimitMiddleware


logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info(
        "starting_asr_service",
        version=settings.APP_VERSION,
        debug=settings.DEBUG
    )
    
    # Initialize database
    from app.services.database import init_db
    await init_db()
    
    # Initialize storage
    from app.services.storage import init_storage
    await init_storage()
    
    yield
    
    # Shutdown
    logger.info("shutting_down_asr_service")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Production-grade ASR service with OpenAI-compatible API",
    docs_url="/docs" if settings.ENABLE_DOCS else None,
    redoc_url="/redoc" if settings.ENABLE_DOCS else None,
    openapi_url="/openapi.json" if settings.ENABLE_DOCS else None,
    lifespan=lifespan
)

# Middleware (order matters - first added = first executed)
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(LoggingMiddleware)

if settings.RATE_LIMIT_ENABLED:
    app.add_middleware(RateLimitMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset"]
)

# Routers
app.include_router(health.router, tags=["Health"])
app.include_router(openai.router, prefix="/v1", tags=["OpenAI Compatible"])
app.include_router(transcriptions.router, prefix="/api", tags=["Transcriptions"])
app.include_router(models.router, prefix="/api", tags=["Models"])
app.include_router(account.router, prefix="/api", tags=["Account"])
app.include_router(tts.router, prefix="/api", tags=["TTS Proxy"])
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])
app.include_router(websocket.router, tags=["WebSocket"])


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler."""
    logger.error(
        "unhandled_exception",
        error=str(exc),
        path=request.url.path,
        method=request.method
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "message": "Internal server error",
                "type": "internal_error",
                "code": "INTERNAL_ERROR"
            }
        }
    )


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "documentation": "/docs",
        "health": "/api/health"
    }
