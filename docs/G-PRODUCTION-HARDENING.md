# ASR Service - Production Hardening Notes

## GPU Sizing for L4

### NVIDIA L4 Specifications
- **VRAM**: 24 GB
- **CUDA Cores**: 7,424
- **Tensor Cores**: 232 (4th Gen)
- **TDP**: 72W
- **Memory Bandwidth**: 300 GB/s

### Model Memory Requirements

| Model | float16 VRAM | int8 VRAM | Recommended Concurrent |
|-------|--------------|-----------|----------------------|
| tiny  | ~1 GB        | ~0.5 GB   | 8-10                 |
| base  | ~1 GB        | ~0.5 GB   | 8-10                 |
| small | ~2 GB        | ~1 GB     | 4-6                  |
| medium| ~5 GB        | ~2.5 GB   | 2-3                  |
| large-v3 | ~6 GB     | ~3 GB     | 2-3                  |

### Recommended Configuration for L4

```yaml
# GPU Pool Settings
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
    reserved_gb: 2  # System overhead
    eviction_strategy: lru
    warmup_on_startup: true
  compute_type: float16  # Best balance of speed/accuracy
```

### Performance Expectations

| Model | Real-time Factor | 1 Hour Audio |
|-------|------------------|--------------|
| tiny  | 32x              | ~2 minutes   |
| base  | 16x              | ~4 minutes   |
| small | 6x               | ~10 minutes  |
| medium| 2x               | ~30 minutes  |
| large-v3 | 1x            | ~60 minutes  |

---

## Model Quantization & Compute Type Recommendations

### When to Use Each Compute Type

**Float16 (Recommended)**
- Default for most use cases
- Best balance of speed and accuracy
- ~2x faster than float32
- Minimal accuracy loss

**Int8**
- When VRAM is constrained
- High-throughput scenarios
- ~20% faster than float16
- Small accuracy degradation acceptable

**Float32**
- When maximum accuracy is required
- Research/forensic applications
- Slower but most precise

### Quantization Impact on WER (Word Error Rate)

| Model   | Float32 WER | Float16 WER | Int8 WER |
|---------|-------------|-------------|----------|
| tiny    | 18.6%       | 18.7%       | 19.2%    |
| base    | 14.6%       | 14.7%       | 15.1%    |
| small   | 10.3%       | 10.4%       | 10.8%    |
| medium  | 8.1%        | 8.2%        | 8.5%     |
| large-v3| 4.9%        | 5.0%        | 5.3%     |

---

## Concurrency Guidance

### Worker Concurrency Formula

```
max_concurrent_jobs = floor((gpu_vram_gb - reserved_gb) / model_vram_gb)
```

For L4 (24GB) with large-v3 (6GB):
```
max_concurrent = floor((24 - 2) / 6) = 3 jobs
```

### Queue Strategy

```python
# Priority queue configuration
task_routes = {
    'tasks.transcription.*': {
        'queue': 'transcription',
        'routing_key': 'transcription'
    }
}

# Separate queues by priority
task_queues = {
    'transcription.high': {
        'exchange': 'transcription',
        'exchange_type': 'direct',
        'binding_key': 'transcription.high'
    },
    'transcription.normal': {
        'exchange': 'transcription',
        'exchange_type': 'direct',
        'binding_key': 'transcription.normal'
    },
    'transcription.low': {
        'exchange': 'transcription',
        'exchange_type': 'direct',
        'binding_key': 'transcription.low'
    }
}
```

### Auto-scaling Configuration

```yaml
# Kubernetes HPA example
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: asr-worker-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: asr-worker
  minReplicas: 1
  maxReplicas: 10
  metrics:
    - type: External
      external:
        metric:
          name: celery_queue_length
          selector:
            matchLabels:
              queue: transcription
        target:
          type: AverageValue
          averageValue: "10"
```

---

## Caching Strategy

### Multi-Level Caching

```
┌─────────────────────────────────────────────────────────────┐
│                     CACHING LAYERS                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  L1: In-Memory (Worker)                                     │
│  ├── Loaded Whisper models (GPU VRAM)                      │
│  └── LRU eviction (keep hot models)                        │
│  TTL: Infinite (managed by GPU pool)                       │
│                                                             │
│  L2: Redis Cache                                            │
│  ├── Job status/results                                    │
│  ├── Rate limit counters                                   │
│  └── Transcript fragments (streaming)                      │
│  TTL: 1 hour for jobs, 1 minute for fragments              │
│                                                             │
│  L3: MinIO Storage                                          │
│  ├── Audio files (configurable retention)                  │
│  ├── Transcript outputs (JSON/SRT/VTT/TXT)                 │
│  └── Temporary chunks (24h auto-delete)                    │
│  TTL: 7 days default, configurable per-job                 │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Cache Warming

```python
# Preload popular models on startup
@app.on_event("startup")
async def warmup_cache():
    popular_models = ["base", "small"]
    for model in popular_models:
        await preload_model(model)
    
    # Warm Redis with common queries
    await cache_model_list()
    await cache_health_status()
```

---

## Cost Controls

### Resource Quotas per Tenant

```python
TIER_LIMITS = {
    "free": {
        "audio_seconds_per_day": 3600,  # 1 hour
        "max_file_size_mb": 100,
        "max_duration_seconds": 600,  # 10 min
        "concurrent_jobs": 1,
        "allowed_models": ["tiny", "base"],
        "features": {"diarization": False, "word_timestamps": False}
    },
    "pro": {
        "audio_seconds_per_day": 36000,  # 10 hours
        "max_file_size_mb": 500,
        "max_duration_seconds": 7200,  # 2 hours
        "concurrent_jobs": 5,
        "allowed_models": ["tiny", "base", "small", "medium"],
        "features": {"diarization": True, "word_timestamps": True}
    },
    "enterprise": {
        "audio_seconds_per_day": 864000,  # 10 days worth
        "max_file_size_mb": 2000,
        "max_duration_seconds": 28800,  # 8 hours
        "concurrent_jobs": 20,
        "allowed_models": ["tiny", "base", "small", "medium", "large-v3"],
        "features": {"diarization": True, "word_timestamps": True}
    }
}
```

### Cost Estimation Formula

```python
def estimate_cost(audio_seconds: float, model: str, features: dict) -> float:
    """Estimate transcription cost in USD."""
    
    # Base cost per minute by model
    model_rates = {
        "tiny": 0.001,
        "base": 0.002,
        "small": 0.005,
        "medium": 0.010,
        "large-v3": 0.020
    }
    
    minutes = audio_seconds / 60
    base_cost = minutes * model_rates.get(model, 0.002)
    
    # Feature multipliers
    if features.get("diarization"):
        base_cost *= 1.5
    if features.get("word_timestamps"):
        base_cost *= 1.2
    
    return round(base_cost, 4)
```

---

## Abuse Prevention

### Rate Limiting Strategy

```python
# Multi-tier rate limiting
RATE_LIMITS = {
    # Per IP (anonymous)
    "ip": {
        "requests_per_minute": 10,
        "requests_per_hour": 100,
        "uploads_per_day": 5
    },
    # Per API key (authenticated)
    "api_key": {
        "requests_per_minute": 60,
        "requests_per_hour": 1000,
        "audio_seconds_per_day": 86400
    },
    # Per tenant (organization)
    "tenant": {
        "concurrent_jobs": 10,
        "audio_seconds_per_day": 864000
    }
}
```

### Content Validation

```python
async def validate_upload(file: UploadFile) -> ValidationResult:
    # 1. Check file size
    if file.size > MAX_FILE_SIZE:
        raise ValidationError("File too large")
    
    # 2. Check magic numbers (not just extension)
    magic = await file.read(8)
    await file.seek(0)
    
    if not is_valid_audio_magic(magic):
        raise ValidationError("Invalid file format")
    
    # 3. Decode and validate
    try:
        audio = await decode_audio(file)
        if audio.duration > MAX_DURATION:
            raise ValidationError("Audio too long")
    except DecodeError:
        raise ValidationError("Cannot decode audio")
    
    # 4. Check for embedded executables
    if contains_executable(file):
        raise ValidationError("Security violation detected")
    
    return ValidationResult(valid=True)
```

### IP Reputation Check

```python
async def check_ip_reputation(ip: str) -> bool:
    """Check if IP is known bad actor."""
    # Check against blocklist
    if await redis.sismember("ip:blocklist", ip):
        return False
    
    # Check rate of failed requests
    failed_key = f"failed_requests:{ip}"
    failed_count = await redis.incr(failed_key)
    await redis.expire(failed_key, 3600)
    
    if failed_count > 100:  # 100 failed requests in 1 hour
        await redis.sadd("ip:blocklist", ip)
        await alert_security_team(ip)
        return False
    
    return True
```

---

## Security Checklist

### Pre-Deployment

- [ ] Change all default passwords
- [ ] Generate new JWT secret (256-bit random)
- [ ] Enable TLS 1.2+ only
- [ ] Configure HSTS headers
- [ ] Set up fail2ban for SSH/nginx
- [ ] Disable root SSH login
- [ ] Configure firewall (ufw/iptables)
- [ ] Set up log aggregation (ELK/Loki)
- [ ] Enable audit logging
- [ ] Configure backup strategy

### API Security

- [ ] API keys stored as bcrypt hashes
- [ ] Rate limiting enabled
- [ ] Request size limits configured
- [ ] CORS properly configured
- [ ] Input validation on all endpoints
- [ ] SQL injection prevention (parameterized queries)
- [ ] XSS protection headers
- [ ] CSRF tokens for UI

### Infrastructure

- [ ] Non-root containers
- [ ] Read-only filesystems where possible
- [ ] Secrets in Docker secrets/env vars (not in images)
- [ ] Network segmentation
- [ ] GPU isolation (if multi-tenant)
- [ ] Resource limits (CPU/memory)
- [ ] Health checks configured
- [ ] Graceful shutdown handling

### Monitoring & Alerting

- [ ] Prometheus metrics collection
- [ ] Grafana dashboards
- [ ] AlertManager rules
- [ ] Error tracking (Sentry)
- [ ] Uptime monitoring
- [ ] Log retention policy
- [ ] Security event alerting

---

## Future Roadmap

### Phase 2: Enhanced Features
- [ ] Batch transcription endpoint (multiple files)
- [ ] Webhook signing for security
- [ ] Real-time streaming improvements
- [ ] Custom vocabulary/fine-tuning
- [ ] Noise robustness improvements

### Phase 3: Enterprise Features
- [ ] Multi-region deployment
- [ ] Advanced analytics dashboard
- [ ] SSO integration (SAML/OIDC)
- [ ] Audit trail export
- [ ] Compliance certifications (SOC2, HIPAA)

### Phase 4: Advanced Capabilities
- [ ] Live translation
- [ ] Sentiment analysis
- [ ] Topic extraction
- [ ] PII redaction
- [ ] Custom model training

---

## Disaster Recovery

### Backup Strategy

```bash
# Database backup (daily)
pg_dump -h postgres -U asr asr > backup_$(date +%Y%m%d).sql

# MinIO backup (weekly)
mc mirror asr-storage backup/asr-storage

# Configuration backup
 tar czf config_backup.tar.gz docker-compose.yml .env nginx/
```

### Recovery Procedures

1. **Database Failure**
   ```bash
   # Restore from backup
   psql -h postgres -U asr asr < backup_YYYYMMDD.sql
   ```

2. **Worker Failure**
   ```bash
   # Scale up new workers
   docker-compose up -d --scale worker=3
   ```

3. **Complete Failure**
   ```bash
   # Restore from backup
   docker-compose down
   # Restore data volumes
   docker-compose up -d
   ```

---

## Performance Tuning

### Database Optimization

```sql
-- Add indexes for common queries
CREATE INDEX CONCURRENTLY idx_jobs_tenant_status 
    ON jobs(tenant_id, status, created_at DESC);

CREATE INDEX CONCURRENTLY idx_usage_tenant_period 
    ON usage_metering(tenant_id, period_day);

-- Partition large tables
CREATE TABLE job_events_2024 PARTITION OF job_events
    FOR VALUES FROM ('2024-01-01') TO ('2025-01-01');
```

### Redis Optimization

```conf
# redis.conf
maxmemory 2gb
maxmemory-policy allkeys-lru
save ""  # Disable RDB for cache-only use
appendonly no
```

### Worker Optimization

```python
# Celery optimization
celery_app.conf.update(
    worker_prefetch_multiplier=1,  # For GPU tasks
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_max_tasks_per_child=100,  # Restart after 100 tasks
)
```
