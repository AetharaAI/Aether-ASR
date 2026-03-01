# ASR Service - Production-Grade Speech-to-Text

A complete, production-ready Speech-to-Text (ASR) service with OpenAI-compatible API, GPU acceleration, and enterprise features.

## Features

- **OpenAI-Compatible API**: Drop-in replacement for Whisper API
- **GPU Acceleration**: Optimized for NVIDIA L4 GPUs using faster-whisper
- **Async Processing**: Handle large files with job queue and progress tracking
- **Real-time Streaming**: WebSocket endpoint for live transcription
- **Enterprise Security**: API key auth, rate limiting, audit logging
- **Multi-tenant**: Tenant isolation with configurable quotas
- **Flexible Output**: JSON, SRT, VTT, TXT formats
- **Optional Features**: VAD, speaker diarization, word-level timestamps

## Architecture

```
┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐
│   UI    │────▶│  Nginx  │────▶│ FastAPI │────▶│  Redis  │
│ (React) │     │ (Proxy) │     │  (API)  │     │ (Queue) │
└─────────┘     └─────────┘     └─────────┘     └────┬────┘
                                                       │
                              ┌────────────────────────┘
                              │
                              ▼
                       ┌─────────────┐
                       │    GPU      │
                       │   Worker    │
                       │   (Celery)  │
                       └──────┬──────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
         ┌─────────┐    ┌─────────┐    ┌─────────┐
         │Postgres │    │  MinIO  │    │ Whisper │
         │(Metadata│    │ (Audio) │    │  Models │
         └─────────┘    └─────────┘    └─────────┘
```

## Quick Start

### Prerequisites

- Docker & Docker Compose
- NVIDIA Docker Runtime (for GPU support)
- NVIDIA GPU with CUDA 12.1+ support

### 1. Clone and Configure

```bash
git clone <repository>
cd asr-service

# Copy and edit environment file
cp .env.example .env
# Edit .env with your settings
```

### 2. Start Services

```bash
cd infra

# Start core services
docker-compose up -d

# With monitoring (Prometheus + Grafana)
docker-compose --profile monitoring up -d
```

### 3. Verify Installation

```bash
# Check health
curl http://localhost:8000/api/health

# Get API version
curl http://localhost:8000/api/version
```

### 4. Access UI

Open http://localhost:3000 in your browser.

Default API key: `test-key-change-in-production`

## API Usage

### OpenAI-Compatible Endpoint

```bash
# Transcribe audio file
curl -X POST http://localhost:8000/v1/audio/transcriptions \
  -H "X-API-Key: your-api-key" \
  -F "file=@audio.mp3" \
  -F "model=whisper-1" \
  -F "response_format=json"
```

### Async Job Creation

```bash
# Create async job (for large files)
curl -X POST http://localhost:8000/api/transcriptions \
  -H "X-API-Key: your-api-key" \
  -F "file=@long-audio.mp3" \
  -F "model=large-v3" \
  -F "diarization_enabled=true"

# Check job status
curl http://localhost:8000/api/transcriptions/job_xxx \
  -H "X-API-Key: your-api-key"

# Download result
curl http://localhost:8000/api/transcriptions/job_xxx/download?format=srt \
  -H "X-API-Key: your-api-key" \
  --output transcript.srt
```

### WebSocket Streaming

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/transcribe?api_key=your-key&model=base');

ws.onopen = () => {
  // Send audio chunks
  ws.send(audioChunk);
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Transcript:', data.text);
};
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | postgresql+asyncpg://asr:asr@postgres:5432/asr | PostgreSQL connection |
| `REDIS_URL` | redis://redis:6379/0 | Redis connection |
| `MINIO_ENDPOINT` | minio:9000 | MinIO/S3 endpoint |
| `JWT_SECRET` | - | JWT signing secret |
| `WHISPER_DEFAULT_MODEL` | base | Default Whisper model |
| `MAX_FILE_SIZE_MB` | 500 | Max upload size |
| `CELERY_WORKER_CONCURRENCY` | 2 | Concurrent GPU jobs |

### Model Selection

| Model | VRAM | Speed | Accuracy | Use Case |
|-------|------|-------|----------|----------|
| tiny  | 1GB  | 32x   | Basic    | Quick drafts |
| base  | 1GB  | 16x   | Good     | General use |
| small | 2GB  | 6x    | Better   | Professional |
| medium| 5GB  | 2x    | Very Good| High quality |
| large-v3 | 6GB | 1x | Best     | Maximum accuracy |

## GPU Requirements

### NVIDIA L4 (Recommended)
- 24GB VRAM
- Supports 3-4 concurrent large-v3 models
- Or 8-10 concurrent base models

### Other GPUs
| GPU | VRAM | Concurrent large-v3 |
|-----|------|---------------------|
| A100 | 40GB | 6 |
| A10 | 24GB | 3 |
| T4 | 16GB | 2 |
| RTX 4090 | 24GB | 3 |

## Production Deployment

### 1. SSL/TLS Setup

```bash
# Using Let's Encrypt
certbot --nginx -d asr.yourdomain.com
```

### 2. Nginx Configuration

Copy `infra/nginx/asr.conf` to `/etc/nginx/sites-available/asr` and enable:

```bash
ln -s /etc/nginx/sites-available/asr /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx
```

### 3. Security Hardening

See [docs/G-PRODUCTION-HARDENING.md](docs/G-PRODUCTION-HARDENING.md) for:
- GPU sizing recommendations
- Rate limiting configuration
- Abuse prevention
- Security checklist

### 4. Monitoring

```bash
# Enable Prometheus + Grafana
docker-compose --profile monitoring up -d

# Access Grafana at http://localhost:3001
# Default credentials: admin/admin
```

## Development

### API Development

```bash
cd api
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Worker Development

```bash
cd worker
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
celery -A app.celery_app worker --loglevel=info
```

### UI Development

```bash
cd ui
npm install
npm run dev
```

## Testing

```bash
# Run API tests
cd api
pytest

# Run worker tests
cd worker
pytest

# Load testing (requires locust)
cd tests/load
locust -f locustfile.py
```

## Documentation

- [Architecture Overview](docs/A-ARCHITECTURE-OVERVIEW.md)
- [API Specification](docs/B-API-SPECIFICATION.md)
- [Data Model](docs/C-DATA-MODEL.md)
- [Processing Pipeline](docs/D-PROCESSING-PIPELINE.md)
- [Implementation Plan](docs/E-IMPLEMENTATION-PLAN.md)
- [Production Hardening](docs/G-PRODUCTION-HARDENING.md)

## License

MIT License - See LICENSE file for details.

## Support

For issues and feature requests, please use GitHub Issues.

For enterprise support, contact: support@yourdomain.com
