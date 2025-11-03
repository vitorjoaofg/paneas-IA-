"""Authentication schemas."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr


class UserInfo(BaseModel):
    """User information response."""

    id: UUID
    email: EmailStr
    name: str
    picture: Optional[str] = None
    google_id: str
    is_active: bool
    created_at: datetime
    last_login_at: Optional[datetime] = None


class TokenResponse(BaseModel):
    """JWT token response."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class LogoutResponse(BaseModel):
    """Logout response."""

    message: str
