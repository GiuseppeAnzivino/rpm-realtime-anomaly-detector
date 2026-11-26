"""
PRESENTATION LAYER (AUTHENTICATION ROUTES)
Description: HTTP endpoints for login, refresh and logout of the Auth-Service microservice.
Responsibility: Translates HTTP requests into calls to the authentication service and business errors into HTTP status codes.
Independence: Contains no business logic and no data access: it only wires the request to the service.
"""

from collections.abc import Iterator

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from api.schemas import LoginRequest, LogoutRequest, RefreshRequest, TokenResponse
from business.service import AuthService
from business.exceptions import AuthenticationError
from data.repository import RefreshTokenRepository, UserRepository

router = APIRouter(prefix="/auth", tags=["auth"])


#region Dependencies

def get_session(request: Request) -> Iterator[Session]:
    """
        Provide one database session per request, closed at the end.

        The session factory is stored in the application state at startup.
    """
    with request.app.state.session_factory() as session:
        yield session


def get_auth_service(
    request: Request, session: Session = Depends(get_session)
) -> AuthService:
    """
        Build the authentication service for the current request.

        The token settings are loaded once at startup and stored in the
        application state.
    """
    return AuthService(
        UserRepository(session),
        RefreshTokenRepository(session),
        request.app.state.token_settings,
    )

#endregion


#region Endpoints

@router.post("/login", response_model=TokenResponse)
def login(
    body: LoginRequest, service: AuthService = Depends(get_auth_service)
) -> TokenResponse:
    """
        Authenticate a user.

        Returns:
            The access token, the refresh token and the access token lifetime.

        Raises:
            HTTPException: 401 if the credentials are wrong or the account is disabled.
    """
    try:
        result = service.login(body.email, body.password)
    except AuthenticationError:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return TokenResponse(
        access_token=result.access_token,
        refresh_token=result.refresh_token,
        expires_in=result.expires_in,
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh(
    body: RefreshRequest, service: AuthService = Depends(get_auth_service)
) -> TokenResponse:
    """
        Exchange a refresh token for a new access token and refresh token.

        The presented refresh token is revoked and cannot be used again.

        Returns:
            The new access token, the new refresh token and the access token lifetime.

        Raises:
            HTTPException: 401 if the refresh token is invalid, expired or revoked.
    """
    try:
        result = service.refresh(body.refresh_token)
    except AuthenticationError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    return TokenResponse(
        access_token=result.access_token,
        refresh_token=result.refresh_token,
        expires_in=result.expires_in,
    )


@router.post("/logout", status_code=204)
def logout(
    body: LogoutRequest, service: AuthService = Depends(get_auth_service)
) -> None:
    """
        Revoke a refresh token.

        Idempotent: an unknown or already revoked token still returns 204.
        The access token stays valid until it expires (15 minutes), because
        access tokens are stateless.
    """
    service.logout(body.refresh_token)

#endregion