# ASR Service - Executive Architecture Overview

## Component Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                                    CLIENT LAYER                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐            │
│  │   Web UI     │  │   cURL/API   │  │  SDK Client  │  │   WebSocket  │            │
│  │  (React)     │  │   Client     │  │              │  │   Client     │            │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘            │
└─────────┼─────────────────┼─────────────────┼─────────────────┼────────────────────┘
          │                 │                 │                 │
          └─────────────────┴────────┬────────┴─────────────────┘
                                     │
┌────────────────────────────────────┼────────────────────────────────────────────────┐
│                              NGINX REVERSE PROXY                                    │
│  ┌─────────────────────────────────┼─────────────────────────────────────────────┐  │
│  │  - TLS termination              │                                             │  │
│  │  - Rate limiting (layer 1)      │                                             │  │
│  │  - Static file serving (UI)     │                                             │  │
│  │  - WebSocket upgrade handling   │                                             │  │
│  │  - Upload size limits (500MB)   │                                             │  │
│  └─────────────────────────────────┼─────────────────────────────────────────────┘  │
└────────────────────────────────────┼────────────────────────────────────────────────┘
                                     │
┌────────────────────────────────────┼────────────────────────────────────────────────┐
│                              API LAYER (FastAPI)                                    │
│  ┌─────────────────────────────────┼─────────────────────────────────────────────┐  │
│  │  ┌─────────────┐  ┌─────────────┐│┌─────────────┐  ┌─────────────────────┐   │  │
│  │  │   Auth      │  │   OpenAI    │││  Industrial │  │      WebSocket      │   │  │
│  │  │ Middleware  │  │  Endpoints  │││  Endpoints  │  │   /ws/transcribe    │   │  │
│  │  │  (API Key)  │  │             │││             │  │                     │   │  │
│  │  └─────────────┘  └─────────────┘│└─────────────┘  └─────────────────────┘   │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐   │  │
│  │  │   Jobs      │  │   Models    │  │   Health    │  │      Metrics        │   │  │
│  │  │  Manager    │  │   Registry  │  │   Checks    │  │   (/api/metrics)    │   │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────────┘   │  │
│  └─────────────────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     │ Enqueues Jobs
                                     │
┌────────────────────────────────────┼────────────────────────────────────────────────┐
│                           MESSAGE QUEUE (Redis)                                     │
│  ┌─────────────────────────────────┼─────────────────────────────────────────────┐  │
│  │  - Job queues (priority: high/normal/low)                                      │  │
│  │  - Rate limiting counters (sliding window)                                     │  │
│  │  - WebSocket pub/sub for progress updates                                      │  │
│  │  - Result caching (transcript fragments)                                       │  │
│  └─────────────────────────────────┼─────────────────────────────────────────────┘  │
└────────────────────────────────────┼────────────────────────────────────────────────┘
                                     │
                                     │ Pulls Jobs
                                     │
┌────────────────────────────────────┼────────────────────────────────────────────────┐
│                           WORKER LAYER (Celery)                                     │
│  ┌─────────────────────────────────┼─────────────────────────────────────────────┐  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐   │  │
│  │  │   VAD       │  │   Chunk     │  │  faster-    │  │   Post-Process      │   │  │
│  │  │ (Silero)    │  │   Engine    │  │  whisper    │  │   (merge/align)     │   │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────────┘   │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐   │  │
│  │  │ Diarization │  │   Word      │  │   Format    │  │   Store Results     │   │  │
│  │  │  (optional) │  │  Alignment  │  │  (srt/vtt)  │  │  (MinIO + Postgres) │   │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────────┘   │  │
│  └─────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                       │
│  ┌─────────────────────────────────────────────────────────────────────────────┐     │
│  │                         GPU POOL (NVIDIA L4)                                 │     │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │     │
│  │  │  Model 1    │  │  Model 2    │  │  Model 3    │  │   Model N           │  │     │
│  │  │  (tiny)     │  │  (base)     │  │  (small)    │  │   (large-v3)        │  │     │
│  │  │  ~1GB VRAM  │  │  ~1GB VRAM  │  │  ~2GB VRAM  │  │   ~6GB VRAM         │  │     │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────────┘  │     │
│  │                                                                              │     │
│  │  GPU Memory: 24GB (L4)                                                       │     │
│  │  Concurrent models: 2-4 large-v3, or 8-12 smaller models                     │     │
│  └─────────────────────────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     │ Stores
                                     │
┌────────────────────────────────────┼────────────────────────────────────────────────┐
│                              DATA LAYER                                             │
│  ┌────────────────────┐  ┌────────────────────┐  ┌────────────────────────────────┐ │
│  │    Postgres        │  │      MinIO         │  │          Redis                 │ │
│  │  (Metadata/State)  │  │  (Audio/Artifacts) │  │      (Cache/Queue)             │ │
│  │                    │  │                    │  │                                │ │
│  │  - tenants         │  │  - raw audio       │  │  - job queues                  │ │
│  │  - api_keys        │  │  - transcripts     │  │  - rate limit counters         │ │
│  │  - jobs            │  │  - exports (srt)   │  │  - ws channels                 │ │
│  │  - job_events      │  │  - temp chunks     │  │  - result cache                │ │
│  │  - usage_metering  │  │  - diarization     │  │                                │ │
│  │  - presets         │  │                    │  │                                │ │
│  └────────────────────┘  └────────────────────┘  └────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

## Data Flow: Upload to Result

```
┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐
│  UPLOAD │────▶│   VAD   │────▶│  CHUNK  │────▶│   ASR   │────▶│  POST   │
│  AUDIO  │     │   PRE   │     │  ENGINE │     │  ENGINE │     │  PROC   │
└─────────┘     └─────────┘     └─────────┘     └─────────┘     └────┬────┘
     │                                                                 │
     │  1. Client uploads audio (or records)                          │
     │  2. API validates, stores to MinIO, creates job in Postgres    │
     │  3. Job enqueued to Redis queue                                │
     │                                                                 │
     │  4. Worker pulls job, downloads audio from MinIO               │
     │  5. VAD (Silero) segments audio, removes silence               │
     │  6. Chunking: split by duration + overlap                      │
     │  7. Each chunk → faster-whisper (GPU)                          │
     │  8. Optional: diarization → speaker labels                     │
     │  9. Optional: word alignment → word timestamps                 │
     │  10. Merge segments, format output                             │
     │                                                                 │
     │  11. Store transcript to MinIO                                 │
     │  12. Update job status in Postgres                             │
     │  13. Emit job events (WebSocket/SSE)                           │
     │                                                                 ▼
     │                                                          ┌─────────┐
     │                                                          │  STORE  │
     └─────────────────────────────────────────────────────────▶│ RESULT  │
                                                                │ RETURN  │
                                                                └─────────┘
```

## Processing Modes

### Mode 1: Synchronous (Small Files < 30 seconds)
```
Client ──POST /v1/audio/transcriptions──▶ API ──Direct Processing──▶ GPU ──Immediate Response──▶ Client
                                         (bypass queue)
```
- Timeout: 60 seconds
- Max file size: 25MB
- Use case: Short recordings, real-time needs

### Mode 2: Asynchronous (Large Files / Batch)
```
Client ──POST /api/transcriptions───────▶ API ──Create Job──▶ Redis Queue
                                              └──────────────┘
Client ◀──Job ID────────────────────────────────────────────┘

Client ──GET /api/transcriptions/{id}───▶ API ──Poll Status──▶ Postgres
                                              (or SSE/WebSocket push)
```
- No timeout limit
- Max file size: 500MB (configurable)
- Use case: Podcasts, meetings, long recordings

### Mode 3: Streaming (Real-time / WebSocket)
```
Client ──WS /ws/transcribe──────────────▶ API
       ──Audio Chunk 1─────────────────▶     ──Partial──▶ GPU
       ──Audio Chunk 2─────────────────▶     ──Partial──▶ GPU
       ◀──Transcript Update────────────┘     ◀──────────┘
       ◀──Final Transcript─────────────┘
```
- Chunk size: 100-500ms audio
- Latency: < 500ms end-to-end
- Use case: Live transcription, captions

## GPU Model Lifecycle & Pooling Strategy

### Model Loading Strategy

```
┌─────────────────────────────────────────────────────────────────┐
│                    GPU MODEL POOL                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐         │
│  │   WARM      │    │   WARM      │    │   COLD      │         │
│  │   (tiny)    │◄──►│   (base)    │    │  (large-v3) │         │
│  │  Loaded     │    │  Loaded     │    │  On-demand  │         │
│  │  VRAM: 1GB  │    │  VRAM: 1GB  │    │  VRAM: 6GB  │         │
│  └─────────────┘    └─────────────┘    └─────────────┘         │
│        │                  │                  │                  │
│        │                  │                  │                  │
│        ▼                  ▼                  ▼                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              NVIDIA L4 GPU (24GB VRAM)                   │   │
│  │  ┌─────────────────────────────────────────────────────┐ │   │
│  │  │  Reserved: 2GB (system)                             │ │   │
│  │  │  Models: 2GB (tiny + base preloaded)                │ │   │
│  │  │  Available: 20GB for dynamic loading                │ │   │
│  │  │  → Can load 3x large-v3 concurrently                │ │   │
│  │  └─────────────────────────────────────────────────────┘ │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
│  LRU Eviction: When VRAM full, unload least recently used       │
│  Preload on Startup: tiny, base (configurable)                  │
│  Lazy Load: small, medium, large-v3 on first request            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Model Specifications (faster-whisper)

| Model | Parameters | VRAM (float16) | VRAM (int8) | Speed | Accuracy |
|-------|------------|----------------|-------------|-------|----------|
| tiny | 39M | ~1GB | ~500MB | ~32x | Basic |
| base | 74M | ~1GB | ~500MB | ~16x | Good |
| small | 244M | ~2GB | ~1GB | ~6x | Better |
| medium | 769M | ~5GB | ~2.5GB | ~2x | Very Good |
| large-v3 | 1550M | ~6GB | ~3GB | 1x | Best |

### Pooling Configuration

```yaml
# GPU Pool Settings for L4 (24GB)
gpu_pool:
  max_concurrent_jobs: 4
  preload_models:
    - tiny
    - base
  lazy_load_models:
    - small
    - medium
    - large-v3
  vram_management:
    reserved_gb: 2
    eviction_strategy: lru
    warmup_on_startup: true
  compute_type: float16  # or int8 for more capacity
```

## Technology Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| Frontend | React 18 + TypeScript + Tailwind | Web UI |
| API | FastAPI + Uvicorn | REST API + WebSocket |
| ASR Engine | faster-whisper | GPU transcription |
| VAD | silero-vad | Voice activity detection |
| Diarization | pyannote.audio (optional) | Speaker separation |
| Alignment | whisper-timestamped (optional) | Word timestamps |
| Queue | Celery + Redis | Async job processing |
| Database | PostgreSQL 15 | Metadata, state |
| Storage | MinIO | Audio, transcripts |
| Cache | Redis | Rate limiting, sessions |
| Monitoring | Prometheus + Grafana | Metrics, dashboards |
| Proxy | Nginx | TLS, routing, static files |
| Container | Docker + NVIDIA Container Toolkit | GPU support |

## Security Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        SECURITY LAYERS                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Layer 1: Transport                                              │
│  ├── TLS 1.3 (Nginx)                                             │
│  ├── HSTS headers                                                │
│  └── Certificate pinning (optional)                              │
│                                                                  │
│  Layer 2: Authentication                                         │
│  ├── API Key (header: X-API-Key) for programmatic access         │
│  ├── JWT (Bearer token) for UI sessions                          │
│  └── Key rotation support                                        │
│                                                                  │
│  Layer 3: Authorization                                          │
│  ├── Role-based: admin, user, readonly                           │
│  ├── Tenant isolation (multi-tenant)                             │
│  └── Resource-level permissions                                  │
│                                                                  │
│  Layer 4: Rate Limiting                                          │
│  ├── Per-API-key sliding window (Redis)                          │
│  ├── Tier-based: free, pro, enterprise                           │
│  └── Burst allowance with exponential backoff                    │
│                                                                  │
│  Layer 5: Input Validation                                       │
│  ├── File type whitelist (mp3, wav, m4a, ogg, flac)              │
│  ├── File size limits                                            │
│  ├── Magic number validation (not just extension)                │
│  └── Content scanning (ClamAV optional)                          │
│                                                                  │
│  Layer 6: Audit & Compliance                                     │
│  ├── Request logging (structured JSON)                           │
│  ├── Audit trail for all operations                              │
│  └── Data retention policies                                     │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Deployment Topology

```
┌─────────────────────────────────────────────────────────────────┐
│                         PRODUCTION                                │
│                                                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │   Nginx     │  │   Nginx     │  │   Nginx     │  (LB Layer)  │
│  │  (Primary)  │  │ (Secondary) │  │  (Health)   │              │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘              │
│         └─────────────────┴─────────────────┘                    │
│                           │                                      │
│         ┌─────────────────┴─────────────────┐                    │
│         ▼                                 ▼                      │
│  ┌─────────────┐                  ┌─────────────┐                │
│  │  API Pod 1  │◄────────────────►│  API Pod 2  │                │
│  │  (FastAPI)  │   Shared State   │  (FastAPI)  │                │
│  └──────┬──────┘   (Postgres/     └──────┬──────┘                │
│         │            Redis)              │                       │
│         └─────────────────┬───────────────┘                       │
│                           │                                      │
│         ┌─────────────────┴─────────────────┐                    │
│         ▼                                 ▼                      │
│  ┌─────────────┐                  ┌─────────────┐                │
│  │ Worker Pod 1│                  │ Worker Pod 2│                │
│  │  (Celery)   │                  │  (Celery)   │                │
│  │  + GPU L4   │                  │  + GPU L4   │                │
│  └─────────────┘                  └─────────────┘                │
│                                                                  │
│  Shared Services: Postgres, Redis, MinIO                        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Performance Targets

| Metric | Target | Notes |
|--------|--------|-------|
| API Response Time (sync) | < 2s | For 30s audio |
| Async Job Start | < 5s | Queue to worker |
| WebSocket Latency | < 500ms | Chunk to partial |
| Throughput | 10x realtime | 1 hour audio in 6 min |
| GPU Utilization | > 80% | During peak |
| Availability | 99.9% | Excluding maintenance |
| Concurrent Jobs | 4-8 | Per L4 GPU |
