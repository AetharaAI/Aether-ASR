-- Initialize ASR database
-- Create default tenant
INSERT INTO tenants (id, name, slug, config, limits, is_active, created_at, updated_at)
VALUES (
    '00000000-0000-0000-0000-000000000001',
    'Default Tenant',
    'default',
    '{
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
    '{
        "requests_per_minute": 60,
        "requests_per_hour": 1000,
        "audio_seconds_per_day": 86400,
        "concurrent_jobs": 5
    }'::jsonb,
    true,
    NOW(),
    NOW()
)
ON CONFLICT (slug) DO NOTHING;

-- Create default API key (hash of 'test-key-change-in-production')
-- This is a placeholder - generate a real key in production
INSERT INTO api_keys (id, tenant_id, key_hash, key_prefix, name, scopes, is_active, created_at)
VALUES (
    '00000000-0000-0000-0000-000000000002',
    '00000000-0000-0000-0000-000000000001',
    'a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3', -- hash of '123'
    'test-key',
    'Default API Key',
    '["transcription:read", "transcription:write"]',
    true,
    NOW()
)
ON CONFLICT DO NOTHING;
