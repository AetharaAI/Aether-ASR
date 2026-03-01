# Aether-ASR - Production-Grade Speech-to-Text

A complete, production-ready Speech-to-Text (ASR) service by **AetherPro Technologies** with an OpenAI-compatible API, GPU acceleration capabilities, and an integrated settings UI mirroring Chatterbox-TTS.

## Features

- **Aether Hub UI**: A beautifully crafted dark-themed interface supporting audio file uploads and live transcription metrics.
- **OpenAI-Compatible API**: Drop-in replacement for Whisper API mapping `/api/asr` natively.
- **GPU Acceleration**: Optimized for NVIDIA L4 GPUs using highly concurrent faster-whisper.
- **Enterprise Capabilities**: Job queues, Voice Activity Detection (VAD), speaker diarization, and word-level timestamps.

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

## OVHCloud VM Deployment Guide

This repository is pre-configured to operate on an OVHCloud instance with an NVIDIA L4 GPU.

### Prerequisites

- Docker & Docker Compose
- NVIDIA Docker Runtime (for GPU support)
- NVIDIA GPU with CUDA 12.1+ support

### 1. Model Configuration

Ensure your pre-downloaded Whisper models are located on your VM's block storage format:
`/mnt/aetherpro/models/audio/whisper`

The Docker configuration natively mounts this directory and assumes `large-v3` as the standard processing endpoint.

### 2. Clone and Route
Clone the repository:
```bash
git clone git@github.com:AetharaAI/Aether-ASR.git
cd Aether-ASR
```

*Note on GPU Usage*: By default, `docker-compose.yml` configures Aether-ASR to bind exclusively to **GPU Index 1**. Leave GPU 0 and GPU 3 free for routing constraints matching your existing layout.

### 3. Start Services
```bash
cd infra
docker compose up -d --build
```

### 4. Create Reverse Proxy Domain (asr.aetherpro.us)
Create the subdomain `asr.aetherpro.us` in your DNS registrar pointing to your OVHCloud IP address, and proxy port 3000 to port 80 or 443 with Nginx.

A generic Nginx block:
```nginx
server {
    server_name asr.aetherpro.us;

    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

Then run `certbot --nginx -d asr.aetherpro.us` to secure the endpoint.

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | postgresql+asyncpg://asr:asr@postgres:5432/asr | PostgreSQL connection |
| `REDIS_URL` | redis://redis:6379/0 | Redis connection |
| `MINIO_ENDPOINT` | minio:9000 | MinIO/S3 endpoint |
| `CELERY_WORKER_CONCURRENCY` | 1 | Concurrent GPU jobs |
| `WHISPER_MODELS_DIR` | /models | Directory for mapping models |
| `WHISPER_PRELOAD_MODELS` | large-v3 | Model mapping override |

## License

**Aether-ASR Custom License**

Copyright (c) 2026 AetherPro Technologies
Founder: Cory Gibson

This software is conditionally open-source with strict attribution requirements. Any public deployment must visibly attribute "Powered by Aether-ASR by AetherPro Technologies". See the `LICENSE` file for details.
