-- Migration: API Keys Management System
-- Description: Create tables for API key management with usage tracking

-- Create api_keys table
CREATE TABLE IF NOT EXISTS api.api_keys (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    key_hash TEXT NOT NULL UNIQUE,
    key_prefix TEXT NOT NULL, -- Store "sk-proj-xxxx" for display purposes
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    is_admin BOOLEAN NOT NULL DEFAULT FALSE,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_used_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ,
    revoked_by UUID REFERENCES api.api_keys(id)
);

-- Add api_key_id to existing tables for usage tracking
ALTER TABLE api.request_audit
ADD COLUMN IF NOT EXISTS api_key_id UUID REFERENCES api.api_keys(id);

ALTER TABLE api.model_usage
ADD COLUMN IF NOT EXISTS api_key_id UUID REFERENCES api.api_keys(id);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_api_keys_key_hash ON api.api_keys (key_hash) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_api_keys_is_active ON api.api_keys (is_active);
CREATE INDEX IF NOT EXISTS idx_api_keys_created_at ON api.api_keys (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_request_audit_api_key_id ON api.request_audit (api_key_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_model_usage_api_key_id ON api.model_usage (api_key_id, created_at DESC);

-- Create view for API key usage analytics
CREATE OR REPLACE VIEW api.api_key_usage_stats AS
SELECT
    k.id,
    k.name,
    k.key_prefix,
    k.is_active,
    k.is_admin,
    k.created_at,
    k.last_used_at,
    COUNT(DISTINCT ra.id) as total_requests,
    COALESCE(SUM(mu.tokens_prompt), 0) as total_tokens_prompt,
    COALESCE(SUM(mu.tokens_completion), 0) as total_tokens_completion,
    COALESCE(AVG(ra.latency_ms), 0) as avg_latency_ms,
    COUNT(DISTINCT ra.id) FILTER (WHERE ra.created_at > NOW() - INTERVAL '24 hours') as requests_24h,
    COUNT(DISTINCT ra.id) FILTER (WHERE ra.created_at > NOW() - INTERVAL '7 days') as requests_7d,
    COUNT(DISTINCT ra.id) FILTER (WHERE ra.created_at > NOW() - INTERVAL '30 days') as requests_30d
FROM api.api_keys k
LEFT JOIN api.request_audit ra ON ra.api_key_id = k.id
LEFT JOIN api.model_usage mu ON mu.api_key_id = k.id
GROUP BY k.id, k.name, k.key_prefix, k.is_active, k.is_admin, k.created_at, k.last_used_at;

-- Grant necessary permissions
GRANT SELECT, INSERT, UPDATE ON api.api_keys TO aistack;
GRANT SELECT ON api.api_key_usage_stats TO aistack;
