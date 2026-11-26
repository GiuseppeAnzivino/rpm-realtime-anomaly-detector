"""
BUSINESS LAYER (ACCESS TOKENS)
Description: Configuration, creation and verification of JWT access tokens for the Auth-Service microservice.
Responsibility: Reads the signing secret and the token lifetime from environment variables, signs short-lived access tokens and validates them.
Independence: Depends only on the PyJWT library and the standard library; it knows nothing about users, persistence, or HTTP.
"""

import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt

from business.exceptions import InvalidTokenError

ACCESS_TOKEN_TYPE = "access"
MIN_SECRET_LENGTH = 32


#region Token Settings

@dataclass(frozen=True)
class TokenSettings:
    """
        Immutable settings used to sign and verify access tokens.

        Attributes:
            jwt_secret: The secret used to sign and verify access tokens.
            jwt_algorithm: The JWT signing algorithm.
            access_token_minutes: Lifetime of an access token, in minutes.
    """

    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 15


def get_token_settings() -> TokenSettings:
    """
        Build the token settings from the environment.

        Reads JWT_SECRET (required) and, optionally, ACCESS_TOKEN_MINUTES.

        Returns:
            The validated settings.

        Raises:
            RuntimeError: If JWT_SECRET is missing or shorter than
                ``MIN_SECRET_LENGTH`` characters.
    """
    secret = os.environ.get("JWT_SECRET", "")
    if not secret:
        raise RuntimeError("JWT_SECRET is not set")
    if len(secret) < MIN_SECRET_LENGTH:
        raise RuntimeError(
            f"JWT_SECRET must be at least {MIN_SECRET_LENGTH} characters long"
        )
    return TokenSettings(
        jwt_secret=secret,
        access_token_minutes=int(os.environ.get("ACCESS_TOKEN_MINUTES", "15")),
    )

#endregion


#region Access Tokens

def create_access_token(
    user_id: uuid.UUID,
    role: str,
    settings: TokenSettings,
    now: datetime | None = None,
) -> str:
    """
        Create a signed JWT access token.

        The token carries the user identifier (``sub``), the role, the token
        type and the issue and expiry times.

        Args:
            user_id: The identifier of the authenticated user.
            role: The role of the user, as a string.
            settings: The token settings.
            now: The issue time; defaults to the current UTC time.

        Returns:
            The encoded JWT.
    """
    now = now or datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "role": role,
        "type": ACCESS_TOKEN_TYPE,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str, settings: TokenSettings) -> dict:
    """
        Verify an access token and return its claims.

        Args:
            token: The encoded JWT.
            settings: The token settings.

        Returns:
            The decoded claims.

        Raises:
            InvalidTokenError: If the token is malformed, expired, signed with
                another key, missing required claims, or not an access token.
    """
    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["exp", "sub"]},
        )
    except jwt.PyJWTError as error:
        raise InvalidTokenError(str(error)) from error
    if claims.get("type") != ACCESS_TOKEN_TYPE:
        raise InvalidTokenError("Wrong token type")
    return claims

#endregion