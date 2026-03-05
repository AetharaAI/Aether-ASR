"""Pydantic settings configuration for ASR API."""
from pydantic_settings import BaseSettings
from typing import List, Optional
from pydantic import field_validator
import os


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Application
    APP_NAME: str = "ASR Service"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENABLE_DOCS: bool = False
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 1
    
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://asr:asr@postgres:5432/asr"
    DATABASE_POOL_SIZE: int = 10
    
    # Redis
    REDIS_URL: str = "redis://redis:6379/0"
    
    # Storage (MinIO)
    MINIO_ENDPOINT: str = "minio:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "asr-storage"
    MINIO_SECURE: bool = False
    
    # Security
    API_KEY_HEADER: str = "X-API-Key"
    JWT_SECRET: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 24
    
    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = False
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = 60
    RATE_LIMIT_REQUESTS_PER_HOUR: int = 1000
    
    # ASR Models
    WHISPER_MODELS_DIR: str = "/models"
    WHISPER_DEFAULT_MODEL: str = "large-v3"
    WHISPER_COMPUTE_TYPE: str = "float16"
    WHISPER_DEVICE: str = "cuda"
    WHISPER_PRELOAD_MODELS: str = "large-v3"
    
    @property
    def whisper_preload_models_list(self) -> List[str]:
        """Get preload models as a list."""
        return [m.strip() for m in self.WHISPER_PRELOAD_MODELS.split(",") if m.strip()]
    
    # Processing
    MAX_FILE_SIZE_MB: int = 500
    MAX_DURATION_SECONDS: int = 7200
    DEFAULT_RETENTION_DAYS: int = 7
    SYNC_MAX_DURATION_SECONDS: int = 30
    
    # VAD
    VAD_ENABLED: bool = True
    VAD_THRESHOLD: float = 0.5
    VAD_MIN_SPEECH_DURATION_MS: int = 250
    
    # Chunking
    CHUNK_LENGTH_SECONDS: int = 30
    CHUNK_OVERLAP_SECONDS: int = 5
    
    # Celery
    CELERY_BROKER_URL: str = "redis://redis:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/2"
    CELERY_WORKER_CONCURRENCY: int = 2
    
    # Webhook
    WEBHOOK_TIMEOUT_SECONDS: int = 30
    WEBHOOK_MAX_RETRIES: int = 3
    
    # Observability
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"
    METRICS_ENABLED: bool = True
    TRACING_ENABLED: bool = False
    
    # TTS Upstream (Chatterbox)
    TTS_BASE_URL: str = "https://tts.aetherpro.us"
    TTS_API_KEY: str = ""
    TTS_MODEL: str = "chatterbox"
    TTS_TIMEOUT_SECONDS: int = 120
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
