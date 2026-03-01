# ASR Service - Data Model

## Entity Relationship Diagram

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│    tenants      │     │    api_keys     │     │    presets      │
├─────────────────┤     ├─────────────────┤     ├─────────────────┤
│ id (PK)         │◄────┤ tenant_id (FK)  │     │ id (PK)         │
│ name            │     │ id (PK)         │     │ tenant_id (FK)  │─◄┐
│ slug            │     │ key_hash        │     │ name            │  │
│ config          │     │ name            │     │ config          │  │
│ limits          │     │ scopes          │     │ is_default      │  │
│ created_at      │     │ rate_limit      │     │ created_at      │  │
│ updated_at      │     │ created_at      │     │ updated_at      │  │
└─────────────────┘     └─────────────────┘     └─────────────────┘  │
         │                      │                                    │
         │                      │         ┌──────────────────────────┘
         │                      │         │
         │              ┌───────┴───────┐ │
         │              │               │ │
         │              ▼               │ │
         │     ┌─────────────────┐      │ │
         │     │  usage_metering │      │ │
         │     ├─────────────────┤      │ │
         │     │ id (PK)         │      │ │
         │     │ tenant_id (FK)  │──────┘ │
         │     │ api_key_id (FK) │        │
         │     │ job_id (FK)     │────────┘
         │     │ audio_seconds   │
         │     │ audio_bytes     │
         │     │ model           │
         │     │ features        │
         │     │ cost_estimate   │
         │     │ recorded_at     │
         │     └─────────────────┘
         │
         │              ┌─────────────────┐
         │              │      jobs       │
         └─────────────►├─────────────────┤
                        │ id (PK)         │
                        │ tenant_id (FK)  │
                        │ api_key_id (FK) │
                        │ preset_id (FK)  │──┘
                        │ status          │
                        │ config          │
                        │ file_info       │
                        │ progress        │
                        │ result          │
                        │ error           │
                        │ usage           │
                        │ retention_until │
                        │ created_at      │
                        │ started_at      │
                        │ completed_at    │
                        │ cancelled_at    │
                        └────────┬────────┘
                                 │
                    ┌────────────┼────────────┐
                    │            │            │
                    ▼            ▼            ▼
           ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
           │   job_events    │  │    artifacts    │  │  audit_logs     │
           ├─────────────────┤  ├─────────────────┤  ├─────────────────┤
           │ id (PK)         │  │ id (PK)         │  │ id (PK)         │
           │ job_id (FK)     │  │ job_id (FK)     │  │ tenant_id (FK)  │
           │ event_type      │  │ type            │  │ api_key_id (FK) │
           │ data            │  │ format          │  │ job_id (FK)     │
           │ created_at      │  │ storage_path    │  │ action          │
           └─────────────────┘  │ size_bytes      │  │ resource_type   │
                                │ checksum        │  │ resource_id     │
                                │ created_at      │  │ details         │
                                └─────────────────┘  │ ip_address      │
                                                     │ user_agent      │
                                                     │ created_at      │
                                                     └─────────────────┘
```

---

## Schema Definitions

### tenants
Multi-tenant organization table.

```sql
CREATE TABLE tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    
    -- Configuration
    config JSONB NOT NULL DEFAULT '{
        "default_model": "base",
        "default_compute_type": "float16",
        "max_file_size_mb": 500,
        "max_duration_seconds": 7200,
        "default_retention_days": 7,
        "allowed_models": ["tiny", "base", "small", "medium", "large-v3"],
        "features": {
            "vad_enabled": true,
            "diarization_enabled": false,
            "word_timestamps": true
        }
    }'::jsonb,
    
    -- Rate limits and quotas
    limits JSONB NOT NULL DEFAULT '{
        "requests_per_minute": 60,
        "requests_per_hour": 1000,
        "audio_seconds_per_day": 86400,
        "concurrent_jobs": 5
    }'::jsonb,
    
    -- Status
    is_active BOOLEAN NOT NULL DEFAULT true,
    is_deleted BOOLEAN NOT NULL DEFAULT false,
    
    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);

-- Indexes
CREATE INDEX idx_tenants_slug ON tenants(slug);
CREATE INDEX idx_tenants_active ON tenants(is_active) WHERE is_active = true;
```

### api_keys
API authentication keys per tenant.

```sql
CREATE TABLE api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    
    -- Key storage (hash only, never store plaintext)
    key_hash VARCHAR(255) UNIQUE NOT NULL,
    key_prefix VARCHAR(8) NOT NULL, -- First 8 chars for identification
    
    -- Metadata
    name VARCHAR(255) NOT NULL,
    description TEXT,
    
    -- Scopes and permissions
    scopes JSONB NOT NULL DEFAULT '["transcription:read", "transcription:write"]'::jsonb,
    
    -- Rate limiting (override tenant defaults if set)
    rate_limit JSONB DEFAULT '{
        "requests_per_minute": 60,
        "requests_per_hour": 1000
    }'::jsonb,
    
    -- Expiration
    expires_at TIMESTAMPTZ,
    last_used_at TIMESTAMPTZ,
    
    -- Status
    is_active BOOLEAN NOT NULL DEFAULT true,
    is_revoked BOOLEAN NOT NULL DEFAULT false,
    
    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    revoked_at TIMESTAMPTZ,
    revoked_reason TEXT
);

-- Indexes
CREATE INDEX idx_api_keys_tenant ON api_keys(tenant_id);
CREATE INDEX idx_api_keys_hash ON api_keys(key_hash);
CREATE INDEX idx_api_keys_active ON api_keys(is_active, is_revoked) WHERE is_active = true AND is_revoked = false;
```

### jobs
Transcription jobs table.

```sql
CREATE TYPE job_status AS ENUM (
    'pending',      -- Queued, waiting for worker
    'processing',   -- Active processing
    'completed',    -- Success
    'failed',       -- Error occurred
    'cancelled',    -- User cancelled
    'expired'       -- Retention period exceeded
);

CREATE TABLE jobs (
    id VARCHAR(32) PRIMARY KEY, -- ULID format: job_ + 26 chars
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    api_key_id UUID REFERENCES api_keys(id) ON DELETE SET NULL,
    preset_id UUID REFERENCES presets(id) ON DELETE SET NULL,
    
    -- Status
    status job_status NOT NULL DEFAULT 'pending',
    
    -- Configuration (snapshot at creation time)
    config JSONB NOT NULL DEFAULT '{
        "model": "base",
        "language": "auto",
        "compute_type": "float16",
        "vad_enabled": true,
        "vad_threshold": 0.5,
        "diarization_enabled": false,
        "word_timestamps": false,
        "chunk_length": 30,
        "chunk_overlap": 5,
        "output_format": "json",
        "webhook_url": null,
        "retention_days": 7
    }'::jsonb,
    
    -- Input file info
    file_info JSONB NOT NULL DEFAULT '{
        "original_name": null,
        "storage_key": null,
        "size_bytes": 0,
        "duration_seconds": null,
        "format": null,
        "sample_rate": null,
        "channels": null
    }'::jsonb,
    
    -- Progress tracking
    progress JSONB NOT NULL DEFAULT '{
        "percent": 0,
        "current_step": "queued",
        "steps_total": 5,
        "chunks_processed": 0,
        "chunks_total": 0,
        "message": "Waiting in queue"
    }'::jsonb,
    
    -- Result (populated on completion)
    result JSONB DEFAULT NULL,
    
    -- Error (populated on failure)
    error JSONB DEFAULT NULL,
    
    -- Usage metrics
    usage JSONB DEFAULT NULL,
    
    -- Retention
    retention_until TIMESTAMPTZ,
    
    -- Webhook
    webhook_url VARCHAR(2048),
    webhook_delivered_at TIMESTAMPTZ,
    webhook_attempts INT DEFAULT 0,
    
    -- Metadata
    client_ip INET,
    user_agent TEXT,
    
    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    failed_at TIMESTAMPTZ,
    cancelled_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ
);

-- Indexes
CREATE INDEX idx_jobs_tenant ON jobs(tenant_id);
CREATE INDEX idx_jobs_status ON jobs(status);
CREATE INDEX idx_jobs_tenant_status ON jobs(tenant_id, status);
CREATE INDEX idx_jobs_created_at ON jobs(created_at DESC);
CREATE INDEX idx_jobs_retention ON jobs(retention_until) WHERE retention_until IS NOT NULL;
CREATE INDEX idx_jobs_expires ON jobs(expires_at) WHERE expires_at IS NOT NULL;

-- Partial indexes for common queries
CREATE INDEX idx_jobs_pending ON jobs(status) WHERE status = 'pending';
CREATE INDEX idx_jobs_processing ON jobs(status) WHERE status = 'processing';
CREATE INDEX idx_jobs_active ON jobs(status) WHERE status IN ('pending', 'processing');
```

### job_events
Event stream for job lifecycle.

```sql
CREATE TYPE job_event_type AS ENUM (
    'created',
    'queued',
    'started',
    'vad_complete',
    'chunking_complete',
    'transcribing_progress',
    'transcribing_complete',
    'diarization_complete',
    'alignment_complete',
    'formatting_complete',
    'completed',
    'failed',
    'cancelled',
    'webhook_sent',
    'webhook_failed',
    'retention_expired'
);

CREATE TABLE job_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id VARCHAR(32) NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    event_type job_event_type NOT NULL,
    data JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_job_events_job ON job_events(job_id);
CREATE INDEX idx_job_events_type ON job_events(event_type);
CREATE INDEX idx_job_events_created ON job_events(created_at DESC);

-- Partitioning recommendation for high volume:
-- PARTITION BY RANGE (created_at) with monthly partitions
```

### artifacts
Stored output files (transcripts, exports).

```sql
CREATE TYPE artifact_type AS ENUM (
    'transcript_json',
    'transcript_srt',
    'transcript_vtt',
    'transcript_txt',
    'audio_original',
    'audio_processed',
    'diarization',
    'alignment'
);

CREATE TABLE artifacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id VARCHAR(32) NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    type artifact_type NOT NULL,
    format VARCHAR(10) NOT NULL, -- json, srt, vtt, txt, mp3, wav, etc.
    
    -- Storage
    storage_path VARCHAR(1024) NOT NULL, -- MinIO path
    size_bytes BIGINT NOT NULL,
    checksum VARCHAR(64), -- SHA-256
    
    -- Metadata
    metadata JSONB DEFAULT '{}'::jsonb,
    
    -- Access tracking
    download_count INT DEFAULT 0,
    last_downloaded_at TIMESTAMPTZ,
    
    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ
);

-- Indexes
CREATE INDEX idx_artifacts_job ON artifacts(job_id);
CREATE INDEX idx_artifacts_type ON artifacts(type);
CREATE INDEX idx_artifacts_expires ON artifacts(expires_at) WHERE expires_at IS NOT NULL;
```

### presets
Saved configuration presets per tenant.

```sql
CREATE TABLE presets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    
    name VARCHAR(255) NOT NULL,
    description TEXT,
    
    -- Configuration snapshot
    config JSONB NOT NULL,
    
    -- Is this the default preset for new jobs?
    is_default BOOLEAN NOT NULL DEFAULT false,
    
    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Unique constraint per tenant
    UNIQUE(tenant_id, name)
);

-- Indexes
CREATE INDEX idx_presets_tenant ON presets(tenant_id);
CREATE INDEX idx_presets_default ON presets(tenant_id, is_default) WHERE is_default = true;
```

### usage_metering
Aggregated usage metrics for billing.

```sql
CREATE TABLE usage_metering (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    api_key_id UUID REFERENCES api_keys(id) ON DELETE SET NULL,
    job_id VARCHAR(32) REFERENCES jobs(id) ON DELETE SET NULL,
    
    -- Usage data
    audio_seconds DECIMAL(10, 2) NOT NULL,
    audio_bytes BIGINT NOT NULL,
    model VARCHAR(50) NOT NULL,
    
    -- Features used
    features JSONB NOT NULL DEFAULT '{}'::jsonb,
    -- e.g., {"vad": true, "diarization": false, "word_timestamps": true}
    
    -- Cost estimation (can be updated later with actual costs)
    cost_estimate DECIMAL(10, 6),
    cost_currency VARCHAR(3) DEFAULT 'USD',
    
    -- Time period for aggregation
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    period_hour TIMESTAMPTZ NOT NULL DEFAULT DATE_TRUNC('hour', NOW()),
    period_day DATE NOT NULL DEFAULT CURRENT_DATE,
    period_month DATE NOT NULL DEFAULT DATE_TRUNC('month', CURRENT_DATE)::DATE,
    
    -- Metadata
    region VARCHAR(50),
    worker_id VARCHAR(100)
);

-- Indexes for aggregation queries
CREATE INDEX idx_usage_tenant ON usage_metering(tenant_id);
CREATE INDEX idx_usage_recorded ON usage_metering(recorded_at DESC);
CREATE INDEX idx_usage_period_hour ON usage_metering(tenant_id, period_hour);
CREATE INDEX idx_usage_period_day ON usage_metering(tenant_id, period_day);
CREATE INDEX idx_usage_period_month ON usage_metering(tenant_id, period_month);

-- Partial index for unbilled usage
CREATE INDEX idx_usage_unbilled ON usage_metering(tenant_id, recorded_at) 
    WHERE cost_estimate IS NULL;
```

### audit_logs
Security audit trail.

```sql
CREATE TYPE audit_action AS ENUM (
    'job.create',
    'job.read',
    'job.cancel',
    'job.delete',
    'artifact.download',
    'api_key.create',
    'api_key.revoke',
    'preset.create',
    'preset.update',
    'preset.delete',
    'login',
    'logout',
    'config.update'
);

CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE SET NULL,
    api_key_id UUID REFERENCES api_keys(id) ON DELETE SET NULL,
    job_id VARCHAR(32) REFERENCES jobs(id) ON DELETE SET NULL,
    
    action audit_action NOT NULL,
    resource_type VARCHAR(50) NOT NULL,
    resource_id VARCHAR(255),
    
    -- Request details
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    
    -- Client info
    ip_address INET,
    user_agent TEXT,
    
    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_audit_tenant ON audit_logs(tenant_id);
CREATE INDEX idx_audit_action ON audit_logs(action);
CREATE INDEX idx_audit_resource ON audit_logs(resource_type, resource_id);
CREATE INDEX idx_audit_created ON audit_logs(created_at DESC);

-- Partitioning strongly recommended:
-- PARTITION BY RANGE (created_at) with monthly partitions
```

---

## Indexes Summary

### Performance-Critical Indexes

```sql
-- Job lookups by tenant and status (dashboard, polling)
CREATE INDEX idx_jobs_tenant_status_created 
    ON jobs(tenant_id, status, created_at DESC);

-- Active jobs for worker queue
CREATE INDEX idx_jobs_pending_created 
    ON jobs(created_at) 
    WHERE status = 'pending';

-- API key lookup (authentication)
CREATE INDEX idx_api_keys_hash_active 
    ON api_keys(key_hash) 
    WHERE is_active = true AND is_revoked = false;

-- Usage aggregation (billing)
CREATE INDEX idx_usage_tenant_period 
    ON usage_metering(tenant_id, period_day, period_month);

-- Artifact downloads
CREATE INDEX idx_artifacts_job_type 
    ON artifacts(job_id, type);
```

### Full-Text Search (Optional)

```sql
-- For searching transcript content
CREATE INDEX idx_jobs_result_text_search 
    ON jobs USING GIN(to_tsvector('english', result->>'text'));
```

---

## Retention & Cleanup Strategy

### Automated Cleanup Jobs

```sql
-- 1. Soft-delete expired jobs (runs daily)
UPDATE jobs 
SET status = 'expired', 
    retention_until = NULL 
WHERE retention_until < NOW() 
  AND status NOT IN ('expired', 'cancelled');

-- 2. Hard-delete old job events (runs monthly, keep 90 days)
DELETE FROM job_events 
WHERE created_at < NOW() - INTERVAL '90 days';

-- 3. Hard-delete old audit logs (runs monthly, keep 1 year)
DELETE FROM audit_logs 
WHERE created_at < NOW() - INTERVAL '1 year';

-- 4. Delete orphaned artifacts from MinIO (runs daily)
-- Application-level job that:
--   a. Finds artifacts with job_id not in active jobs
--   b. Deletes from MinIO
--   c. Deletes from artifacts table
```

### Partitioning Strategy

For high-volume deployments, partition these tables:

```sql
-- job_events - partition by month
CREATE TABLE job_events_y2024m01 PARTITION OF job_events
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

-- usage_metering - partition by month
CREATE TABLE usage_metering_y2024m01 PARTITION OF usage_metering
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

-- audit_logs - partition by month
CREATE TABLE audit_logs_y2024m01 PARTITION OF audit_logs
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');
```

---

## MinIO Object Structure

```
asr-storage/
├── tenants/
│   └── {tenant_id}/
│       ├── audio/
│       │   └── {job_id}/
│       │       └── original.{ext}
│       ├── transcripts/
│       │   └── {job_id}/
│       │       ├── transcript.json
│       │       ├── transcript.srt
│       │       ├── transcript.vtt
│       │       └── transcript.txt
│       ├── temp/
│       │   └── {job_id}/
│       │       ├── chunks/
│       │       │   └── chunk_{n}.wav
│       │       └── vad_segments.json
│       └── diarization/
│           └── {job_id}/
│               └── speakers.json
```

**Lifecycle Policies:**
- `temp/*`: Delete after 24 hours
- `audio/*`: Delete based on retention_days (default 7 days)
- `transcripts/*`: Delete based on retention_days
- `diarization/*`: Delete based on retention_days
