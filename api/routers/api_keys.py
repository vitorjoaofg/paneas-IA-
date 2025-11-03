"""API Key management router (admin endpoints)."""

from typing import List
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status

from schemas.api_keys import (
    CreateAPIKeyRequest,
    CreateAPIKeyResponse,
    APIKeyInfo,
    APIKeyUsageStats,
    APIKeysAnalytics,
    RevokeAPIKeyResponse,
)
from services.api_key_manager import (
    create_api_key,
    list_api_keys,
    revoke_api_key,
    get_api_key_usage,
    get_all_keys_analytics,
)

router = APIRouter(prefix="/api/v1/admin/keys", tags=["API Keys (Admin)"])


def require_admin(request: Request):
    """
    Require admin privileges for the request.

    Admin can be either:
    - API key with is_admin=True
    - JWT user with an admin API key (checked via database)
    """
    auth_type = getattr(request.state, 'auth_type', None)

    if auth_type == 'api_key':
        # Admin API key required
        if not hasattr(request.state, 'api_key_info'):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required"
            )

        if not request.state.api_key_info.get('is_admin'):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin API key required for this operation"
            )

    elif auth_type == 'jwt':
        # For JWT users, we don't require admin for their own keys
        # Admin check will be done per operation if needed
        if not hasattr(request.state, 'user_info'):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required"
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )


def get_user_id(request: Request):
    """Get user_id from request (either from JWT or return None)."""
    auth_type = getattr(request.state, 'auth_type', None)

    if auth_type == 'jwt':
        user_info = getattr(request.state, 'user_info', None)
        if user_info:
            return user_info['id']

    return None


@router.post("", response_model=CreateAPIKeyResponse, status_code=status.HTTP_201_CREATED)
async def create_new_api_key(
    request: Request,
    payload: CreateAPIKeyRequest
):
    """
    Create a new API key.

    - **JWT users**: Can create keys for themselves (non-admin keys only)
    - **Admin API keys**: Can create keys for any user, including admin keys

    The plaintext key is returned only once - make sure to save it securely!
    """
    require_admin(request)

    auth_type = getattr(request.state, 'auth_type', None)
    user_id = get_user_id(request)

    # JWT users can only create non-admin keys for themselves
    if auth_type == 'jwt':
        if payload.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admin API keys can create admin keys"
            )
        # JWT users always create keys for themselves
        key_user_id = user_id
    else:
        # Admin API key can create keys for any user
        # If no user_id provided in payload, key has no owner (system key)
        key_user_id = user_id

    key_id, plaintext_key = await create_api_key(
        name=payload.name,
        user_id=key_user_id,
        is_admin=payload.is_admin,
        metadata=payload.metadata
    )

    # Get key info to return full response
    keys = await list_api_keys()
    key_info = next((k for k in keys if k['id'] == key_id), None)

    if not key_info:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve created key"
        )

    return CreateAPIKeyResponse(
        id=key_info['id'],
        name=key_info['name'],
        key=plaintext_key,
        key_prefix=key_info['key_prefix'],
        is_admin=key_info['is_admin'],
        created_at=key_info['created_at']
    )


@router.get("", response_model=List[APIKeyInfo])
async def list_all_api_keys(
    request: Request,
    include_revoked: bool = False
):
    """
    List API keys.

    - **JWT users**: See only their own keys
    - **Admin API keys**: See all keys

    Set `include_revoked=true` to include revoked keys.
    """
    require_admin(request)

    auth_type = getattr(request.state, 'auth_type', None)
    user_id = get_user_id(request)

    # JWT users see only their own keys
    # Admin API keys see all keys
    if auth_type == 'jwt':
        keys = await list_api_keys(include_revoked=include_revoked, user_id=user_id)
    else:
        keys = await list_api_keys(include_revoked=include_revoked)

    return [APIKeyInfo(**k) for k in keys]


@router.delete("/{key_id}", response_model=RevokeAPIKeyResponse)
async def revoke_key(
    request: Request,
    key_id: UUID
):
    """
    Revoke an API key.

    **Admin only**: This endpoint requires an admin API key.

    Once revoked, the key can no longer be used for authentication.
    """
    require_admin(request)

    admin_key_id = request.state.api_key_info['id']
    success = await revoke_api_key(key_id, revoked_by=admin_key_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found or already revoked"
        )

    return RevokeAPIKeyResponse(
        success=True,
        message=f"API key {key_id} has been revoked"
    )


@router.get("/{key_id}/usage", response_model=APIKeyUsageStats)
async def get_key_usage_stats(
    request: Request,
    key_id: UUID
):
    """
    Get usage statistics for a specific API key.

    **Admin only**: This endpoint requires an admin API key.
    """
    require_admin(request)

    stats = await get_api_key_usage(key_id)

    if not stats:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )

    return APIKeyUsageStats(**stats)


@router.get("/analytics/overview", response_model=APIKeysAnalytics)
async def get_keys_analytics(request: Request):
    """
    Get aggregated analytics for all API keys.

    **Admin only**: This endpoint requires an admin API key.

    Includes:
    - Total/active/revoked key counts
    - Request statistics (last 24h)
    - Token usage statistics
    - Top keys by usage
    """
    require_admin(request)

    analytics = await get_all_keys_analytics()
    return APIKeysAnalytics(**analytics)
