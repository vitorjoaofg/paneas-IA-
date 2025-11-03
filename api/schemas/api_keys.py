"""Schemas for API key management."""

from datetime import datetime
from typing import Dict, Any, Optional, List
from uuid import UUID

from pydantic import BaseModel, Field


class CreateAPIKeyRequest(BaseModel):
    name: str = Field(..., description="Friendly name for the API key", min_length=1, max_length=255)
    is_admin: bool = Field(default=False, description="Whether this key has admin privileges")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Optional metadata")


class CreateAPIKeyResponse(BaseModel):
    id: UUID
    name: str
    key: str = Field(..., description="The plaintext API key - save this, it won't be shown again!")
    key_prefix: str
    is_admin: bool
    created_at: datetime


class APIKeyInfo(BaseModel):
    id: UUID
    name: str
    key_prefix: str
    is_active: bool
    is_admin: bool
    user_id: Optional[UUID] = None
    metadata: Dict[str, Any]
    created_at: datetime
    last_used_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None


class APIKeyUsageStats(BaseModel):
    id: UUID
    name: str
    key_prefix: str
    is_active: bool
    is_admin: bool
    created_at: datetime
    last_used_at: Optional[datetime] = None
    total_requests: int
    total_tokens_prompt: int
    total_tokens_completion: int
    avg_latency_ms: float
    requests_24h: int
    requests_7d: int
    requests_30d: int


class APIKeysAnalytics(BaseModel):
    total_keys: int
    active_keys: int
    revoked_keys: int
    total_requests_24h: int
    avg_latency_ms: float
    unique_endpoints: int
    total_tokens_prompt: int
    total_tokens_completion: int
    total_tokens: int
    top_keys: List[Dict[str, Any]]


class RevokeAPIKeyResponse(BaseModel):
    success: bool
    message: str
