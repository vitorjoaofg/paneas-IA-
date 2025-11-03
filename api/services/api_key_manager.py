"""API Key management service."""

import secrets
import bcrypt
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID

from services.db_client import get_db_connection


def generate_api_key() -> str:
    """
    Generate a new API key in OpenAI format: sk-proj-{32_random_chars}
    """
    random_part = secrets.token_urlsafe(24)[:32]  # Get exactly 32 chars
    return f"sk-proj-{random_part}"


def hash_api_key(key: str) -> str:
    """Hash an API key using bcrypt."""
    return bcrypt.hashpw(key.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def verify_api_key(key: str, key_hash: str) -> bool:
    """Verify an API key against its hash."""
    try:
        return bcrypt.checkpw(key.encode('utf-8'), key_hash.encode('utf-8'))
    except Exception:
        return False


def get_key_prefix(key: str) -> str:
    """Get displayable prefix from API key (e.g., sk-proj-abcd...)."""
    if len(key) > 16:
        return f"{key[:16]}..."
    return key


async def create_api_key(
    name: str,
    user_id: Optional[UUID] = None,
    is_admin: bool = False,
    metadata: Optional[Dict[str, Any]] = None
) -> tuple[UUID, str]:
    """
    Create a new API key.

    Returns:
        Tuple of (key_id, plaintext_key)
    """
    import json
    plaintext_key = generate_api_key()
    key_hash = hash_api_key(plaintext_key)
    key_prefix = get_key_prefix(plaintext_key)

    async with get_db_connection() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO api.api_keys (name, key_hash, key_prefix, is_admin, user_id, metadata)
            VALUES ($1, $2, $3, $4, $5, $6::jsonb)
            RETURNING id
            """,
            name,
            key_hash,
            key_prefix,
            is_admin,
            user_id,
            json.dumps(metadata or {})
        )
        return row['id'], plaintext_key


async def validate_api_key(key: str) -> Optional[Dict[str, Any]]:
    """
    Validate an API key and return key info if valid.

    Returns:
        Dict with key info if valid, None otherwise
    """
    import json
    async with get_db_connection() as conn:
        # Get all active keys (we need to check hash for each one)
        rows = await conn.fetch(
            """
            SELECT id, name, key_hash, is_admin, metadata, created_at, last_used_at
            FROM api.api_keys
            WHERE is_active = TRUE
            """
        )

        for row in rows:
            if verify_api_key(key, row['key_hash']):
                metadata = row['metadata']
                if isinstance(metadata, str):
                    metadata = json.loads(metadata)
                return {
                    'id': row['id'],
                    'name': row['name'],
                    'is_admin': row['is_admin'],
                    'metadata': metadata,
                    'created_at': row['created_at'],
                    'last_used_at': row['last_used_at'],
                }

        return None


async def update_last_used(key_id: UUID) -> None:
    """Update the last_used_at timestamp for a key."""
    async with get_db_connection() as conn:
        await conn.execute(
            """
            UPDATE api.api_keys
            SET last_used_at = NOW()
            WHERE id = $1
            """,
            key_id
        )


async def revoke_api_key(key_id: UUID, revoked_by: Optional[UUID] = None) -> bool:
    """
    Revoke an API key.

    Returns:
        True if key was revoked, False if key not found
    """
    async with get_db_connection() as conn:
        result = await conn.execute(
            """
            UPDATE api.api_keys
            SET is_active = FALSE, revoked_at = NOW(), revoked_by = $2
            WHERE id = $1 AND is_active = TRUE
            """,
            key_id,
            revoked_by
        )
        return result.split()[-1] == '1'  # Check if one row was updated


async def list_api_keys(include_revoked: bool = False, user_id: Optional[UUID] = None) -> List[Dict[str, Any]]:
    """
    List API keys.

    If user_id is provided, only return keys for that user.
    If user_id is None, return all keys (admin function).
    """
    import json
    async with get_db_connection() as conn:
        query = """
            SELECT
                id, name, key_prefix, is_active, is_admin, user_id,
                metadata, created_at, last_used_at, revoked_at
            FROM api.api_keys
        """
        conditions = []
        params = []
        param_num = 1

        if not include_revoked:
            conditions.append("is_active = TRUE")

        if user_id is not None:
            conditions.append(f"user_id = ${param_num}")
            params.append(user_id)
            param_num += 1

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY created_at DESC"

        rows = await conn.fetch(query, *params)
        result = []
        for row in rows:
            row_dict = dict(row)
            # Convert metadata from string to dict if needed
            if isinstance(row_dict.get('metadata'), str):
                row_dict['metadata'] = json.loads(row_dict['metadata'])
            result.append(row_dict)
        return result


async def get_api_key_usage(key_id: UUID) -> Optional[Dict[str, Any]]:
    """Get usage statistics for a specific API key."""
    async with get_db_connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT * FROM api.api_key_usage_stats
            WHERE id = $1
            """,
            key_id
        )
        if row:
            return dict(row)
        return None


async def get_all_keys_analytics() -> Dict[str, Any]:
    """Get aggregated analytics for all API keys."""
    async with get_db_connection() as conn:
        # Total stats
        total_stats = await conn.fetchrow(
            """
            SELECT
                COUNT(DISTINCT id) as total_keys,
                COUNT(DISTINCT id) FILTER (WHERE is_active = TRUE) as active_keys,
                COUNT(DISTINCT id) FILTER (WHERE is_active = FALSE) as revoked_keys
            FROM api.api_keys
            """
        )

        # Request stats (last 24h)
        request_stats = await conn.fetchrow(
            """
            SELECT
                COUNT(DISTINCT id) as total_requests_24h,
                COALESCE(AVG(latency_ms), 0) as avg_latency_ms,
                COUNT(DISTINCT endpoint) as unique_endpoints
            FROM api.request_audit
            WHERE created_at > NOW() - INTERVAL '24 hours'
            """
        )

        # Token usage stats
        token_stats = await conn.fetchrow(
            """
            SELECT
                COALESCE(SUM(tokens_prompt), 0) as total_tokens_prompt,
                COALESCE(SUM(tokens_completion), 0) as total_tokens_completion
            FROM api.model_usage
            WHERE created_at > NOW() - INTERVAL '24 hours'
            """
        )

        # Top keys by usage (last 24h)
        top_keys = await conn.fetch(
            """
            SELECT
                k.id,
                k.name,
                k.key_prefix,
                COUNT(ra.id) as requests_24h
            FROM api.api_keys k
            LEFT JOIN api.request_audit ra ON ra.api_key_id = k.id
                AND ra.created_at > NOW() - INTERVAL '24 hours'
            WHERE k.is_active = TRUE
            GROUP BY k.id, k.name, k.key_prefix
            ORDER BY requests_24h DESC
            LIMIT 10
            """
        )

        return {
            'total_keys': total_stats['total_keys'],
            'active_keys': total_stats['active_keys'],
            'revoked_keys': total_stats['revoked_keys'],
            'total_requests_24h': request_stats['total_requests_24h'],
            'avg_latency_ms': float(request_stats['avg_latency_ms']),
            'unique_endpoints': request_stats['unique_endpoints'],
            'total_tokens_prompt': int(token_stats['total_tokens_prompt']),
            'total_tokens_completion': int(token_stats['total_tokens_completion']),
            'total_tokens': int(token_stats['total_tokens_prompt']) + int(token_stats['total_tokens_completion']),
            'top_keys': [dict(row) for row in top_keys]
        }
