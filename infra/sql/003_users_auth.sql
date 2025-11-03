-- Users authentication table
CREATE TABLE IF NOT EXISTS api.users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    picture TEXT,
    google_id TEXT UNIQUE NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Create index on email for fast lookups
CREATE INDEX IF NOT EXISTS idx_users_email ON api.users(email);
CREATE INDEX IF NOT EXISTS idx_users_google_id ON api.users(google_id);

-- Add user_id to api_keys table (link keys to users)
ALTER TABLE api.api_keys ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES api.users(id);

-- Create index for user's keys lookup
CREATE INDEX IF NOT EXISTS idx_api_keys_user_id ON api.api_keys(user_id);

-- Update the view to include user information
DROP VIEW IF EXISTS api.api_key_usage_stats;

CREATE OR REPLACE VIEW api.api_key_usage_stats AS
SELECT
    k.id, k.name, k.key_prefix, k.is_active, k.is_admin, k.user_id,
    k.created_at, k.last_used_at,
    u.email as user_email,
    u.name as user_name,
    COUNT(DISTINCT ra.id) as total_requests,
    COALESCE(SUM(mu.tokens_prompt), 0) as total_tokens_prompt,
    COALESCE(SUM(mu.tokens_completion), 0) as total_tokens_completion,
    COALESCE(AVG(ra.latency_ms), 0) as avg_latency_ms,
    COUNT(DISTINCT ra.id) FILTER (WHERE ra.created_at > NOW() - INTERVAL '24 hours') as requests_24h,
    COUNT(DISTINCT ra.id) FILTER (WHERE ra.created_at > NOW() - INTERVAL '7 days') as requests_7d,
    COUNT(DISTINCT ra.id) FILTER (WHERE ra.created_at > NOW() - INTERVAL '30 days') as requests_30d
FROM api.api_keys k
LEFT JOIN api.users u ON u.id = k.user_id
LEFT JOIN api.request_audit ra ON ra.api_key_id = k.id
LEFT JOIN api.model_usage mu ON mu.api_key_id = k.id
GROUP BY k.id, u.email, u.name;
