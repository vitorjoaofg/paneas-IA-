"""Authentication service for Google OAuth and JWT tokens."""

import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from uuid import UUID

from jose import JWTError, jwt
from authlib.integrations.starlette_client import OAuth

from config import get_settings
from services.db_client import get_db_connection

settings = get_settings()

# JWT Configuration
SECRET_KEY = settings.jwt_secret_key
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days

# OAuth Configuration
oauth = OAuth()


def configure_oauth():
    """Configure OAuth providers."""
    oauth.register(
        name='google',
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_kwargs={
            'scope': 'openid email profile',
            'prompt': 'select_account',
        }
    )


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    return encoded_jwt


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode and verify a JWT access token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


async def get_or_create_user(google_id: str, email: str, name: str, picture: Optional[str] = None) -> Dict[str, Any]:
    """
    Get existing user or create new user from Google OAuth data.
    Only allows @paneas.com emails.
    """
    # Check if email is from @paneas.com domain
    if not email.endswith('@paneas.com'):
        raise ValueError(f"Only @paneas.com emails are allowed. Got: {email}")

    async with get_db_connection() as conn:
        # Try to find existing user by google_id
        user = await conn.fetchrow(
            """
            SELECT id, email, name, picture, google_id, is_active, created_at, last_login_at
            FROM api.users
            WHERE google_id = $1
            """,
            google_id
        )

        if user:
            # Update last login and picture if changed
            await conn.execute(
                """
                UPDATE api.users
                SET last_login_at = NOW(), picture = $2, name = $3
                WHERE google_id = $1
                """,
                google_id,
                picture,
                name
            )
            return dict(user)

        # Create new user
        user = await conn.fetchrow(
            """
            INSERT INTO api.users (email, name, picture, google_id, last_login_at)
            VALUES ($1, $2, $3, $4, NOW())
            RETURNING id, email, name, picture, google_id, is_active, created_at, last_login_at
            """,
            email,
            name,
            picture,
            google_id
        )

        return dict(user)


async def get_user_by_id(user_id: UUID) -> Optional[Dict[str, Any]]:
    """Get user by ID."""
    async with get_db_connection() as conn:
        user = await conn.fetchrow(
            """
            SELECT id, email, name, picture, google_id, is_active, created_at, last_login_at
            FROM api.users
            WHERE id = $1 AND is_active = TRUE
            """,
            user_id
        )

        if user:
            return dict(user)
        return None


async def check_user_is_admin(user_id: UUID) -> bool:
    """Check if user has any admin API keys (which means they are admin)."""
    async with get_db_connection() as conn:
        result = await conn.fetchval(
            """
            SELECT EXISTS(
                SELECT 1 FROM api.api_keys
                WHERE user_id = $1 AND is_admin = TRUE AND is_active = TRUE
            )
            """,
            user_id
        )
        return result or False
