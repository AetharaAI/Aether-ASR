# ASR Service - Reference Implementation Plan

## Repository Structure

```
asr-service/
├── api/                          # FastAPI backend
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI entry point
│   │   ├── config.py            # Pydantic settings
│   │   ├── dependencies.py      # FastAPI dependencies
│   │   ├── middleware/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py          # API key/JWT auth
│   │   │   ├── rate_limit.py    # Rate limiting
│   │   │   ├── logging.py       # Request logging
│   │   │   └── cors.py          # CORS configuration
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   ├── openai.py        # OpenAI-compatible endpoints
│   │   │   ├── transcriptions.py # Industrial endpoints
│   │   │   ├── models.py        # Model info
│   │   │   ├── health.py        # Health checks
│   │   │   ├── admin.py         # Admin endpoints
│   │   │   └── websocket.py     # WebSocket streaming
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py          # Auth service
│   │   │   ├── storage.py       # MinIO storage
│   │   │   ├── database.py      # Postgres operations
│   │   │   ├── cache.py         # Redis cache
│   │   │   ├── queue.py         # Job queue
│   │   │   ├── metrics.py       # Prometheus metrics
│   │   │   └── webhook.py       # Webhook delivery
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── schemas.py       # Pydantic schemas
│   │   │   └── database.py      # SQLAlchemy models
│   │   └── utils/
│   │       ├── __init__.py
│   │       ├── id_generator.py  # ULID generation
│   │       ├── validators.py    # Input validation
│   │       └── exceptions.py    # Custom exceptions
│   ├── Dockerfile
│   ├── requirements.txt
│   └── pyproject.toml
│
├── worker/                       # Celery worker
│   ├── app/
│   │   ├── __init__.py
│   │   ├── celery_app.py        # Celery configuration
│   │   ├── tasks/
│   │   │   ├── __init__.py
│   │   │   └── transcription.py # Main transcription task
│   │   ├── pipeline/
│   │   │   ├── __init__.py
│   │   │   ├── vad.py           # Silero VAD
│   │   │   ├── chunking.py      # Audio chunking
│   │   │   ├── asr.py           # faster-whisper
│   │   │   ├── diarization.py   # Speaker diarization
│   │   │   ├── alignment.py     # Word alignment
│   │   │   └── postprocess.py   # Output formatting
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── storage.py       # MinIO client
│   │   │   └── database.py      # Postgres client
│   │   └── utils/
│   │       ├── __init__.py
│   │       ├── gpu_manager.py   # GPU model pool
│   │       └── progress.py      # Progress reporting
│   ├── Dockerfile
│   ├── requirements.txt
│   └── pyproject.toml
│
├── ui/                           # React frontend
│   ├── src/
│   │   ├── components/
│   │   │   ├── common/          # Reusable components
│   │   │   ├── upload/          # File upload
│   │   │   ├── recorder/        # Audio recorder
│   │   │   ├── player/          # Audio player
│   │   │   ├── transcript/      # Transcript viewer
│   │   │   ├── jobs/            # Job queue
│   │   │   └── settings/        # Settings forms
│   │   ├── pages/
│   │   │   ├── Home.tsx
│   │   │   ├── Transcribe.tsx
│   │   │   ├── Jobs.tsx
│   │   │   ├── JobDetail.tsx
│   │   │   ├── Settings.tsx
│   │   │   └── Admin.tsx
│   │   ├── hooks/
│   │   │   ├── useApi.ts
│   │   │   ├── useWebSocket.ts
│   │   │   ├── useAuth.ts
│   │   │   └── useJobs.ts
│   │   ├── services/
│   │   │   ├── api.ts
│   │   │   ├── auth.ts
│   │   │   └── storage.ts
│   │   ├── store/
│   │   │   └── index.ts
│   │   ├── types/
│   │   │   └── index.ts
│   │   ├── utils/
│   │   │   ├── formatters.ts
│   │   │   └── validators.ts
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   └── index.css
│   ├── public/
│   ├── index.html
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   └── tailwind.config.js
│
├── infra/                        # Infrastructure
│   ├── docker-compose.yml
│   ├── docker-compose.prod.yml
│   ├── nginx/
│   │   ├── nginx.conf
│   │   └── asr.conf
│   ├── prometheus/
│   │   └── prometheus.yml
│   ├── grafana/
│   │   └── dashboards/
│   └── init-scripts/
│       ├── init-db.sql
│       └── init-minio.sh
│
├── docs/                         # Documentation
│   ├── A-ARCHITECTURE-OVERVIEW.md
│   ├── B-API-SPECIFICATION.md
│   ├── C-DATA-MODEL.md
│   ├── D-PROCESSING-PIPELINE.md
│   ├── E-IMPLEMENTATION-PLAN.md
│   └── G-PRODUCTION-HARDENING.md
│
├── tests/                        # Test suite
│   ├── unit/
│   ├── integration/
│   ├── e2e/
│   └── load/
│
├── scripts/                      # Utility scripts
│   ├── setup.sh
│   ├── migrate.sh
│   └── backup.sh
│
├── .env.example
├── .gitignore
├── Makefile
└── README.md
```

---

## Key Modules & Responsibilities

### API Layer (FastAPI)

| Module | Responsibility |
|--------|----------------|
| `main.py` | Application entry, lifespan management, router registration |
| `config.py` | Environment-based configuration with Pydantic Settings |
| `middleware/auth.py` | API key validation, JWT handling, tenant isolation |
| `middleware/rate_limit.py` | Redis-based sliding window rate limiting |
| `routers/openai.py` | OpenAI-compatible `/v1/audio/*` endpoints |
| `routers/transcriptions.py` | Industrial async job endpoints |
| `routers/websocket.py` | Real-time streaming transcription |
| `services/storage.py` | MinIO upload/download operations |
| `services/queue.py` | Celery job enqueue/dequeue |
| `services/metrics.py` | Prometheus metrics collection |

### Worker Layer (Celery)

| Module | Responsibility |
|--------|----------------|
| `celery_app.py` | Celery configuration, task routing, result backend |
| `tasks/transcription.py` | Main transcription task with retry logic |
| `pipeline/vad.py` | Silero VAD integration |
| `pipeline/asr.py` | faster-whisper model management |
| `pipeline/diarization.py` | pyannote.audio integration (optional) |
| `utils/gpu_manager.py` | Model loading, VRAM management, LRU eviction |
| `utils/progress.py` | Real-time progress reporting via Redis |

### Frontend (React)

| Module | Responsibility |
|--------|----------------|
| `components/upload/` | Drag-drop file upload with progress |
| `components/recorder/` | Web Audio API recording |
| `components/transcript/` | Interactive transcript with timestamps |
| `hooks/useWebSocket.ts` | WebSocket connection management |
| `hooks/useJobs.ts` | Job polling and state management |
| `services/api.ts` | API client with auth interceptors |

---

## Configuration Management (Pydantic Settings)

```python
# api/app/config.py
from pydantic_settings import BaseSettings
from typing import List, Optional

class Settings(BaseSettings):
    # Application
    APP_NAME: str = "ASR Service"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 1
    
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://user:pass@localhost/asr"
    DATABASE_POOL_SIZE: int = 10
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # Storage (MinIO)
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str
    MINIO_SECRET_KEY: str
    MINIO_BUCKET: str = "asr-storage"
    MINIO_SECURE: bool = False
    
    # Security
    API_KEY_HEADER: str = "X-API-Key"
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 24
    
    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = 60
    RATE_LIMIT_REQUESTS_PER_HOUR: int = 1000
    
    # ASR Models
    WHISPER_MODELS_DIR: str = "/models"
    WHISPER_DEFAULT_MODEL: str = "base"
    WHISPER_COMPUTE_TYPE: str = "float16"
    WHISPER_DEVICE: str = "cuda"
    WHISPER_PRELOAD_MODELS: List[str] = ["tiny", "base"]
    
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
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"
    CELERY_WORKER_CONCURRENCY: int = 2
    
    # Webhook
    WEBHOOK_TIMEOUT_SECONDS: int = 30
    WEBHOOK_MAX_RETRIES: int = 3
    
    # Observability
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"
    METRICS_ENABLED: bool = True
    TRACING_ENABLED: bool = False
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
```

---

## Background Job System

### Celery Configuration

```python
# worker/app/celery_app.py
from celery import Celery
from celery.signals import worker_ready, task_prerun, task_postrun

app = Celery('asr_worker')

app.conf.update(
    broker_url=os.getenv('CELERY_BROKER_URL'),
    result_backend=os.getenv('CELERY_RESULT_BACKEND'),
    
    # Serialization
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    
    # Task routing
    task_routes={
        'tasks.transcription.*': {'queue': 'transcription'},
        'tasks.webhook.*': {'queue': 'webhook'},
    },
    
    # Concurrency
    worker_concurrency=int(os.getenv('CELERY_WORKER_CONCURRENCY', 2)),
    worker_prefetch_multiplier=1,  # Important for GPU tasks
    
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
app.autodiscover_tasks(['app.tasks.transcription'])

@worker_ready.connect
def on_worker_ready(**kwargs):
    """Preload models on worker startup."""
    from app.utils.gpu_manager import GPUPool
    GPUPool.warmup()
```

### Task Definition with Idempotency

```python
# worker/app/tasks/transcription.py
from celery import shared_task
from celery.exceptions import MaxRetriesExceededError

@shared_task(
    bind=True,
    queue='transcription',
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
)
def transcribe_audio(self, job_id: str, audio_path: str, config: dict):
    """
    Idempotent transcription task.
    """
    # Check if job already completed (idempotency)
    job = get_job(job_id)
    if job.status == 'completed':
        logger.info(f"Job {job_id} already completed, skipping")
        return job.result
    
    if job.status == 'cancelled':
        logger.info(f"Job {job_id} was cancelled, aborting")
        return None
    
    try:
        # Update status
        update_job_status(job_id, 'processing', progress={'step': 'starting'})
        
        # Run pipeline
        pipeline = TranscriptionPipeline(config)
        result = pipeline.process(
            job_id=job_id,
            audio_path=audio_path,
            progress_callback=report_progress
        )
        
        # Store result
        store_result(job_id, result)
        update_job_status(job_id, 'completed', progress={'percent': 100})
        
        # Send webhook
        if job.webhook_url:
            send_webhook.delay(job_id, job.webhook_url, result)
        
        return result
        
    except Exception as exc:
        logger.exception(f"Transcription failed for job {job_id}")
        
        # Check if retryable
        if is_retryable_error(exc) and self.request.retries < self.max_retries:
            update_job_status(job_id, 'processing', progress={
                'step': 'retrying',
                'attempt': self.request.retries + 1,
                'error': str(exc)
            })
            raise self.retry(exc=exc, countdown=calculate_backoff(self.request.retries))
        
        # Final failure
        update_job_status(job_id, 'failed', error={
            'code': error_code(exc),
            'message': str(exc),
            'retryable': False
        })
        raise
```

---

## Test Plan

### Unit Tests

```python
# tests/unit/test_vad.py
import pytest
from worker.app.pipeline.vad import VADProcessor

class TestVADProcessor:
    def test_detects_speech_segments(self):
        vad = VADProcessor(threshold=0.5)
        audio = load_test_audio("speech_sample.wav")
        
        segments = vad.process(audio)
        
        assert len(segments) > 0
        assert all(s.duration_ms > 0 for s in segments)
    
    def test_respects_threshold(self):
        high_threshold = VADProcessor(threshold=0.9)
        low_threshold = VADProcessor(threshold=0.1)
        
        audio = load_test_audio("quiet_speech.wav")
        
        high_segments = high_threshold.process(audio)
        low_segments = low_threshold.process(audio)
        
        assert len(low_segments) >= len(high_segments)
```

### Integration Tests

```python
# tests/integration/test_api.py
import pytest
import httpx

class TestTranscriptionAPI:
    async def test_create_async_job(self, client: httpx.AsyncClient):
        response = await client.post(
            "/api/transcriptions",
            headers={"X-API-Key": "test_key"},
            files={"file": ("test.mp3", open("tests/fixtures/test.mp3", "rb"))},
            data={"model": "tiny"}
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "pending"
        assert "id" in data
    
    async def test_openai_compatible_endpoint(self, client: httpx.AsyncClient):
        response = await client.post(
            "/v1/audio/transcriptions",
            headers={"X-API-Key": "test_key"},
            files={"file": ("test.mp3", open("tests/fixtures/test.mp3", "rb"))},
            data={"model": "whisper-1", "response_format": "json"}
        )
        
        assert response.status_code == 200
        assert "text" in response.json()
```

### Load Testing

```python
# tests/load/locustfile.py
from locust import HttpUser, task, between

class ASRUser(HttpUser):
    wait_time = between(1, 5)
    
    def on_start(self):
        self.api_key = "test_key"
    
    @task(3)
    def sync_transcription(self):
        with open("fixtures/short_audio.mp3", "rb") as f:
            self.client.post(
                "/v1/audio/transcriptions",
                headers={"X-API-Key": self.api_key},
                files={"file": f},
                data={"model": "tiny"}
            )
    
    @task(1)
    def async_transcription(self):
        with open("fixtures/long_audio.mp3", "rb") as f:
            response = self.client.post(
                "/api/transcriptions",
                headers={"X-API-Key": self.api_key},
                files={"file": f},
                data={"model": "base"}
            )
            job_id = response.json()["id"]
            
            # Poll for completion
            for _ in range(30):
                status = self.client.get(
                    f"/api/transcriptions/{job_id}",
                    headers={"X-API-Key": self.api_key}
                )
                if status.json()["status"] in ["completed", "failed"]:
                    break
```

---

## Security Checklist

### Authentication & Authorization
- [ ] API keys stored as bcrypt hashes only
- [ ] JWT tokens with short expiration
- [ ] Scope-based permissions enforced
- [ ] Tenant isolation verified in all queries

### Input Validation
- [ ] File magic number validation
- [ ] File size limits enforced
- [ ] MIME type whitelist
- [ ] Audio duration limits
- [ ] Path traversal prevention

### Rate Limiting
- [ ] Per-API-key limits implemented
- [ ] Sliding window algorithm
- [ ] Burst handling with 429 responses
- [ ] Header-based limit communication

### Data Protection
- [ ] TLS 1.3 for all connections
- [ ] Encryption at rest (MinIO)
- [ ] Configurable retention policies
- [ ] Secure deletion of expired data

### Audit & Monitoring
- [ ] All requests logged with correlation IDs
- [ ] Failed auth attempts tracked
- [ ] Unusual patterns alerted
- [ ] GDPR/CCPA compliance for data deletion

### Infrastructure
- [ ] Non-root containers
- [ ] Read-only filesystems where possible
- [ ] Secrets in environment variables
- [ ] Network segmentation
- [ ] Regular security updates
