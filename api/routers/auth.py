"""Authentication router for Google OAuth."""

from fastapi import APIRouter, Request, HTTPException, status
from fastapi.responses import RedirectResponse, JSONResponse
from datetime import timedelta

from config import get_settings
from services.auth_service import (
    oauth,
    configure_oauth,
    create_access_token,
    get_or_create_user,
    ACCESS_TOKEN_EXPIRE_MINUTES
)

settings = get_settings()
router = APIRouter(prefix="/auth", tags=["Authentication"])

# Configure OAuth on module load
configure_oauth()


@router.get("/google/login")
async def google_login(request: Request):
    """
    Initiate Google OAuth flow.

    Redirects user to Google login page.
    """
    redirect_uri = settings.google_redirect_uri
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/google/callback")
async def google_callback(request: Request):
    """
    Handle Google OAuth callback.

    - Receives authorization code from Google
    - Exchanges it for user info
    - Validates email domain (@paneas.com only)
    - Creates or updates user in database
    - Generates JWT token
    - Redirects to frontend with token
    """
    try:
        # Get token from Google
        token = await oauth.google.authorize_access_token(request)

        # Get user info from token
        user_info = token.get('userinfo')
        if not user_info:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to get user info from Google"
            )

        google_id = user_info.get('sub')
        email = user_info.get('email')
        name = user_info.get('name', email)
        picture = user_info.get('picture')

        if not google_id or not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing required user information"
            )

        # Get or create user (validates @paneas.com domain)
        try:
            user = await get_or_create_user(google_id, email, name, picture)
        except ValueError as e:
            # Email not from @paneas.com
            return RedirectResponse(
                url=f"/?error=unauthorized&message={str(e)}",
                status_code=status.HTTP_302_FOUND
            )

        # Create JWT token
        access_token = create_access_token(
            data={"sub": str(user['id']), "email": user['email'], "name": user['name']},
            expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        )

        # Redirect to frontend with token
        # Frontend will extract token from URL and store it
        return RedirectResponse(
            url=f"/?token={access_token}",
            status_code=status.HTTP_302_FOUND
        )

    except Exception as e:
        return RedirectResponse(
            url=f"/?error=auth_failed&message={str(e)}",
            status_code=status.HTTP_302_FOUND
        )


@router.get("/me")
async def get_current_user_info(request: Request):
    """
    Get current authenticated user information.

    Requires JWT token in Authorization header.
    """
    # This will be populated by middleware
    if not hasattr(request.state, 'user_info'):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )

    return request.state.user_info


@router.post("/logout")
async def logout():
    """
    Logout endpoint (client-side token removal).

    Since we use stateless JWT tokens, actual logout happens client-side
    by removing the token from storage.
    """
    return {"message": "Logout successful. Please remove token from client storage."}
