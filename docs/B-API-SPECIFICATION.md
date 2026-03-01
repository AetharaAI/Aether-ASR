# ASR Service - API Specification

## Base URL
```
Production: https://asr.yourdomain.com
Local: http://localhost:8000
```

## Authentication

### API Key Authentication (Programmatic Access)
```http
X-API-Key: your_api_key_here
```

### JWT Authentication (UI Sessions)
```http
Authorization: Bearer <jwt_token>
```

### Rate Limit Headers
All responses include rate limit information:
```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1704067200
```

---

## OpenAI-Compatible Endpoints

### POST /v1/audio/transcriptions
Create a transcription from audio file.

**Request**
```http
POST /v1/audio/transcriptions
Content-Type: multipart/form-data
X-API-Key: your_api_key

file: <binary audio data>
model: "whisper-1" | "tiny" | "base" | "small" | "medium" | "large-v3"
language: "en" | "es" | "fr" | ... (optional, auto-detect if omitted)
prompt: "context for transcription" (optional)
response_format: "json" | "text" | "srt" | "verbose_json" | "vtt" (default: json)
temperature: 0.0 - 1.0 (default: 0.0)
timestamp_granularities[]: "word" | "segment" (optional)
```

**Response (json)**
```json
{
  "text": "The quick brown fox jumps over the lazy dog."
}
```

**Response (verbose_json)**
```json
{
  "task": "transcribe",
  "language": "en",
  "duration": 12.5,
  "text": "The quick brown fox jumps over the lazy dog.",
  "words": [
    {
      "word": "The",
      "start": 0.0,
      "end": 0.2
    },
    {
      "word": "quick",
      "start": 0.2,
      "end": 0.5
    }
  ],
  "segments": [
    {
      "id": 0,
      "seek": 0,
      "start": 0.0,
      "end": 3.2,
      "text": "The quick brown fox jumps over the lazy dog.",
      "tokens": [50364, 440, 1168, ...],
      "temperature": 0.0,
      "avg_logprob": -0.234,
      "compression_ratio": 1.5,
      "no_speech_prob": 0.02
    }
  ]
}
```

**Response (srt)**
```srt
1
00:00:00,000 --> 00:00:03,200
The quick brown fox jumps over the lazy dog.
```

**Error Responses**
```json
// 400 Bad Request
{
  "error": {
    "message": "Invalid file format. Supported: mp3, wav, m4a, ogg, flac",
    "type": "invalid_request_error",
    "code": "invalid_file"
  }
}

// 401 Unauthorized
{
  "error": {
    "message": "Invalid API key",
    "type": "authentication_error",
    "code": "invalid_api_key"
  }
}

// 429 Too Many Requests
{
  "error": {
    "message": "Rate limit exceeded. Try again in 60 seconds.",
    "type": "rate_limit_error",
    "code": "rate_limit_exceeded"
  }
}

// 413 Payload Too Large
{
  "error": {
    "message": "File size exceeds 25MB limit for sync endpoint",
    "type": "invalid_request_error",
    "code": "file_too_large"
  }
}
```

---

### POST /v1/audio/translations
Translate audio to English (if non-English).

**Request**
```http
POST /v1/audio/translations
Content-Type: multipart/form-data
X-API-Key: your_api_key

file: <binary audio data>
model: "whisper-1" | "large-v3"
prompt: "context" (optional)
response_format: "json" | "text" | "srt" | "verbose_json" | "vtt"
temperature: 0.0 - 1.0
```

**Response**
Same format as transcriptions endpoint.

---

## Industrial Endpoints

### POST /api/transcriptions
Create an async transcription job (for large files).

**Request**
```http
POST /api/transcriptions
Content-Type: multipart/form-data
X-API-Key: your_api_key

file: <binary audio data>
model: "tiny" | "base" | "small" | "medium" | "large-v3" (default: base)
language: "auto" | "en" | "es" | ... (default: auto)
compute_type: "float16" | "int8" | "float32" (default: float16)
vad_enabled: true | false (default: true)
vad_threshold: 0.5 (default: 0.5)
diARization_enabled: true | false (default: false)
word_timestamps: true | false (default: false)
chunk_length: 30 (seconds, default: 30)
chunk_overlap: 5 (seconds, default: 5)
output_format: "json" | "srt" | "vtt" | "txt" (default: json)
webhook_url: "https://your-callback.com" (optional)
metadata: {"job_name": "Meeting Recording"} (optional)
retention_days: 7 (default: 7, 0 = don't store audio)
```

**Response (201 Created)**
```json
{
  "id": "job_01hqn7x9v8e5j2m4p6r9t0w3y",
  "status": "pending",
  "created_at": "2024-01-15T10:30:00Z",
  "estimated_completion": "2024-01-15T10:32:00Z",
  "file": {
    "name": "meeting.mp3",
    "size": 5242880,
    "duration": 300
  },
  "config": {
    "model": "base",
    "language": "auto",
    "vad_enabled": true,
    "diarization_enabled": false,
    "word_timestamps": false
  },
  "progress": {
    "percent": 0,
    "current_step": "queued",
    "steps_total": 5
  },
  "links": {
    "self": "/api/transcriptions/job_01hqn7x9v8e5j2m4p6r9t0w3y",
    "status": "/api/transcriptions/job_01hqn7x9v8e5j2m4p6r9t0w3y",
    "cancel": "/api/transcriptions/job_01hqn7x9v8e5j2m4p6r9t0w3y/cancel",
    "sse": "/api/transcriptions/job_01hqn7x9v8e5j2m4p6r9t0w3y/events"
  }
}
```

---

### GET /api/transcriptions/{id}
Get job status and results.

**Response (Processing)**
```json
{
  "id": "job_01hqn7x9v8e5j2m4p6r9t0w3y",
  "status": "processing",
  "created_at": "2024-01-15T10:30:00Z",
  "started_at": "2024-01-15T10:30:05Z",
  "progress": {
    "percent": 45,
    "current_step": "transcribing",
    "steps_total": 5,
    "chunks_processed": 4,
    "chunks_total": 10
  },
  "config": { ... }
}
```

**Response (Completed)**
```json
{
  "id": "job_01hqn7x9v8e5j2m4p6r9t0w3y",
  "status": "completed",
  "created_at": "2024-01-15T10:30:00Z",
  "started_at": "2024-01-15T10:30:05Z",
  "completed_at": "2024-01-15T10:31:45Z",
  "duration_seconds": 100.5,
  "config": { ... },
  "result": {
    "language": "en",
    "language_probability": 0.98,
    "duration": 300.5,
    "text": "Full transcript text here...",
    "segments": [
      {
        "id": 0,
        "start": 0.0,
        "end": 5.2,
        "text": "First segment",
        "speaker": "SPEAKER_00",
        "confidence": 0.95,
        "words": [
          {"word": "First", "start": 0.0, "end": 0.3, "confidence": 0.97},
          {"word": "segment", "start": 0.3, "end": 0.8, "confidence": 0.93}
        ]
      }
    ],
    "speakers": ["SPEAKER_00", "SPEAKER_01"]
  },
  "artifacts": {
    "json": "/api/transcriptions/job_01hqn7x9v8e5j2m4p6r9t0w3y/download?format=json",
    "srt": "/api/transcriptions/job_01hqn7x9v8e5j2m4p6r9t0w3y/download?format=srt",
    "vtt": "/api/transcriptions/job_01hqn7x9v8e5j2m4p6r9t0w3y/download?format=vtt",
    "txt": "/api/transcriptions/job_01hqn7x9v8e5j2m4p6r9t0w3y/download?format=txt"
  },
  "usage": {
    "audio_seconds": 300.5,
    "audio_bytes": 5242880,
    "model": "base",
    "compute_type": "float16"
  }
}
```

**Response (Failed)**
```json
{
  "id": "job_01hqn7x9v8e5j2m4p6r9t0w3y",
  "status": "failed",
  "created_at": "2024-01-15T10:30:00Z",
  "started_at": "2024-01-15T10:30:05Z",
  "failed_at": "2024-01-15T10:31:00Z",
  "error": {
    "code": "TRANSCRIPTION_ERROR",
    "message": "Failed to process audio: corrupted file",
    "retryable": false,
    "details": {
      "exception": "AudioDecodeError",
      "traceback": "..."
    }
  }
}
```

---

### GET /api/transcriptions/{id}/download
Download transcript in specified format.

**Request**
```http
GET /api/transcriptions/job_01hqn7x9v8e5j2m4p6r9t0w3y/download?format=srt
X-API-Key: your_api_key
```

**Query Parameters**
- `format`: `json` | `srt` | `vtt` | `txt`

**Response**
Returns the transcript file with appropriate Content-Type.

---

### POST /api/transcriptions/{id}/cancel
Cancel a pending or processing job.

**Request**
```http
POST /api/transcriptions/job_01hqn7x9v8e5j2m4p6r9t0w3y/cancel
X-API-Key: your_api_key
```

**Response (200 OK)**
```json
{
  "id": "job_01hqn7x9v8e5j2m4p6r9t0w3y",
  "status": "cancelled",
  "cancelled_at": "2024-01-15T10:31:00Z",
  "message": "Job cancelled successfully"
}
```

**Response (409 Conflict)**
```json
{
  "error": {
    "code": "INVALID_STATE",
    "message": "Cannot cancel job in state: completed"
  }
}
```

---

### GET /api/transcriptions
List transcription jobs with pagination.

**Request**
```http
GET /api/transcriptions?status=completed&limit=20&offset=0&sort=-created_at
X-API-Key: your_api_key
```

**Query Parameters**
- `status`: Filter by status (pending, processing, completed, failed, cancelled)
- `limit`: Items per page (default: 20, max: 100)
- `offset`: Pagination offset
- `sort`: Sort field (+created_at, -created_at, +completed_at)

**Response**
```json
{
  "items": [
    {
      "id": "job_01hqn7x9v8e5j2m4p6r9t0w3y",
      "status": "completed",
      "created_at": "2024-01-15T10:30:00Z",
      "duration_seconds": 100.5,
      "file_name": "meeting.mp3"
    }
  ],
  "pagination": {
    "total": 150,
    "limit": 20,
    "offset": 0,
    "has_more": true
  }
}
```

---

### GET /api/models
List available models and their capabilities.

**Response**
```json
{
  "models": [
    {
      "id": "tiny",
      "name": "Whisper Tiny",
      "description": "Fastest, lowest accuracy",
      "parameters": "39M",
      "languages": ["en", "es", "fr", "de", "it", "ja", "zh", "..."],
      "capabilities": {
        "transcription": true,
        "translation": true,
        "vad": true,
        "diarization": false,
        "word_timestamps": true
      },
      "resources": {
        "vram_gb": 1,
        "compute_types": ["float16", "int8"]
      }
    },
    {
      "id": "large-v3",
      "name": "Whisper Large v3",
      "description": "Best accuracy, slowest",
      "parameters": "1550M",
      "languages": ["en", "es", "fr", "de", "it", "ja", "zh", "..."],
      "capabilities": {
        "transcription": true,
        "translation": true,
        "vad": true,
        "diarization": true,
        "word_timestamps": true
      },
      "resources": {
        "vram_gb": 6,
        "compute_types": ["float16", "int8", "float32"]
      }
    }
  ]
}
```

---

### GET /api/health
Health check endpoint.

**Response (200 OK)**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2024-01-15T10:30:00Z",
  "services": {
    "database": "connected",
    "redis": "connected",
    "storage": "connected",
    "gpu": {
      "available": true,
      "count": 1,
      "name": "NVIDIA L4",
      "memory": {
        "total_gb": 24,
        "available_gb": 18
      }
    }
  },
  "models": {
    "tiny": {"loaded": true, "warm": true},
    "base": {"loaded": true, "warm": true},
    "small": {"loaded": false, "warm": false},
    "large-v3": {"loaded": false, "warm": false}
  }
}
```

**Response (503 Service Unavailable)**
```json
{
  "status": "degraded",
  "services": {
    "database": "connected",
    "gpu": {"available": false, "error": "CUDA out of memory"}
  }
}
```

---

### GET /api/metrics
Prometheus metrics endpoint.

**Response**
```
# HELP asr_jobs_total Total number of transcription jobs
# TYPE asr_jobs_total counter
asr_jobs_total{status="completed"} 1523
asr_jobs_total{status="failed"} 23

# HELP asr_job_duration_seconds Job processing duration
# TYPE asr_job_duration_seconds histogram
asr_job_duration_seconds_bucket{le="10"} 523
asr_job_duration_seconds_bucket{le="60"} 1200
asr_job_duration_seconds_bucket{le="300"} 1500

# HELP asr_gpu_memory_bytes GPU memory usage
# TYPE asr_gpu_memory_bytes gauge
asr_gpu_memory_bytes{gpu="0"} 6442450944

# HELP asr_audio_processed_seconds_total Total audio processed
# TYPE asr_audio_processed_seconds_total counter
asr_audio_processed_seconds_total 452340
```

---

### GET /api/version
API version information.

**Response**
```json
{
  "version": "1.0.0",
  "api_version": "v1",
  "whisper_version": "20231117",
  "build": {
    "commit": "abc123",
    "branch": "main",
    "timestamp": "2024-01-15T00:00:00Z"
  }
}
```

---

## WebSocket Protocol

### Connection
```
wss://asr.yourdomain.com/ws/transcribe?api_key=your_api_key&model=base&language=auto
```

### Client → Server Messages

**Audio Chunk**
```json
{
  "type": "audio",
  "data": "base64_encoded_audio_chunk",
  "timestamp": 1705312800.123,
  "is_final": false
}
```

**Configuration**
```json
{
  "type": "config",
  "config": {
    "model": "base",
    "language": "en",
    "vad_enabled": true,
    "word_timestamps": false
  }
}
```

**End Stream**
```json
{
  "type": "end",
  "timestamp": 1705312805.456
}
```

### Server → Client Messages

**Partial Transcript**
```json
{
  "type": "partial",
  "text": "The quick brown",
  "timestamp": 1705312800.500,
  "is_final": false
}
```

**Final Transcript**
```json
{
  "type": "final",
  "text": "The quick brown fox jumps over the lazy dog.",
  "timestamp": 1705312801.000,
  "language": "en",
  "confidence": 0.95,
  "segment": {
    "start": 0.0,
    "end": 3.2,
    "text": "The quick brown fox jumps over the lazy dog."
  }
}
```

**Error**
```json
{
  "type": "error",
  "code": "AUDIO_DECODE_ERROR",
  "message": "Failed to decode audio chunk",
  "retryable": true
}
```

**Heartbeat**
```json
{
  "type": "ping",
  "timestamp": 1705312802.000
}
```

### WebSocket Error Codes

| Code | Description | Action |
|------|-------------|--------|
| 1000 | Normal closure | None |
| 1001 | Going away | Reconnect |
| 1008 | Policy violation | Check auth |
| 1011 | Server error | Retry with backoff |
| 1013 | Try again later | Exponential backoff |

---

## Server-Sent Events (SSE)

### GET /api/transcriptions/{id}/events
Subscribe to job progress events.

**Request**
```http
GET /api/transcriptions/job_01hqn7x9v8e5j2m4p6r9t0w3y/events
X-API-Key: your_api_key
Accept: text/event-stream
```

**Event Stream**
```
event: job.created
data: {"id": "job_01hqn7x9v8e5j2m4p6r9t0w3y", "status": "pending"}

event: job.started
data: {"id": "job_01hqn7x9v8e5j2m4p6r9t0w3y", "status": "processing", "started_at": "..."}

event: progress
data: {"percent": 25, "step": "vad", "message": "Running voice activity detection"}

event: progress
data: {"percent": 50, "step": "transcribing", "chunks_processed": 5, "chunks_total": 10}

event: job.completed
data: {"id": "job_01hqn7x9v8e5j2m4p6r9t0w3y", "status": "completed", "result_url": "..."}
```

---

## Error Codes Reference

| Code | HTTP Status | Description | Retryable |
|------|-------------|-------------|-----------|
| `INVALID_REQUEST` | 400 | Malformed request | No |
| `INVALID_FILE` | 400 | Unsupported file format | No |
| `FILE_TOO_LARGE` | 413 | File exceeds size limit | No |
| `INVALID_API_KEY` | 401 | Authentication failed | No |
| `INSUFFICIENT_CREDITS` | 402 | Quota exceeded | No |
| `FORBIDDEN` | 403 | Permission denied | No |
| `NOT_FOUND` | 404 | Resource not found | No |
| `RATE_LIMIT_EXCEEDED` | 429 | Too many requests | Yes (after delay) |
| `TRANSCRIPTION_ERROR` | 500 | Processing failed | Yes |
| `GPU_UNAVAILABLE` | 503 | GPU out of memory | Yes |
| `TIMEOUT` | 504 | Processing timeout | Yes |

---

## Pagination Format

All list endpoints use consistent pagination:

```json
{
  "items": [...],
  "pagination": {
    "total": 1000,
    "limit": 20,
    "offset": 0,
    "has_more": true,
    "next_offset": 20,
    "prev_offset": null
  }
}
```

---

## Webhook Payload

When `webhook_url` is provided:

```json
{
  "event": "transcription.completed",
  "timestamp": "2024-01-15T10:31:45Z",
  "job": {
    "id": "job_01hqn7x9v8e5j2m4p6r9t0w3y",
    "status": "completed",
    "result_url": "https://asr.yourdomain.com/api/transcriptions/job_01hqn7x9v8e5j2m4p6r9t0w3y/download?format=json"
  },
  "signature": "sha256=..."
}
```

Webhook signature verification:
```python
import hmac
import hashlib

expected = hmac.new(
    webhook_secret.encode(),
    payload.encode(),
    hashlib.sha256
).hexdigest()

if f"sha256={expected}" != signature:
    raise ValueError("Invalid signature")
```
