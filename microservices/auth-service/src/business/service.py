"""
BUSINESS LAYER (AUTHENTICATION SERVICE)
Description: Login, refresh and logout logic of the Auth-Service microservice.
Responsibility: Verifies the credentials of a user, issues JWT access tokens together with stored refresh tokens, rotates refresh tokens and revokes them on logout.
Independence: Uses only the repositories, the password module and the token module; it knows nothing about HTTP.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from business.exceptions import InvalidCredentialsError, InvalidTokenError
from business.security import hash_password, needs_rehash, verify_password
from business.tokens import (
    TokenSettings,
    create_access_token,
    generate_refresh_token,
    hash_refresh_token,
)
from data.models import RefreshToken, User
from data.repository import RefreshTokenRepository, UserRepository

# Verified when the user does not exist, so that "unknown email" and
# "wrong password" take the same time and the response does not reveal
# which emails are registered.
_DUMMY_HASH = hash_password("dummy-password")


def _utc_now() -> datetime:
    """Return the current time as a timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def _ensure_utc(value: datetime) -> datetime:
    """
        Return the datetime as timezone-aware UTC.

        Some databases (e.g. SQLite) return naive datetimes even for
        timezone-aware columns; they are interpreted as UTC, which is how
        they are written.

        Args:
            value: The datetime to normalize.

        Returns:
            The same instant, timezone-aware.
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


#region Token Result

@dataclass(frozen=True)
class LoginResult:
    """
        The outcome of a successful login or refresh.

        Attributes:
            access_token: The signed JWT.
            refresh_token: The plaintext refresh token, shown only this once.
            expires_in: Lifetime of the access token, in seconds.
    """

    access_token: str
    refresh_token: str
    expires_in: int

#endregion


#region Authentication Service

class AuthService:
    """
        Implements the login, refresh and logout use cases.

        The clock is injectable so that tests control the issue and expiry times.
    """

    def __init__(
        self,
        users: UserRepository,
        refresh_tokens: RefreshTokenRepository,
        settings: TokenSettings,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        """
            Initialize the service.

            Args:
                users: The repository used to look up users.
                refresh_tokens: The repository used to store and revoke refresh tokens.
                settings: The token settings.
                clock: A function returning the current UTC time.
        """
        self._users = users
        self._refresh_tokens = refresh_tokens
        self._settings = settings
        self._clock = clock

    #region Use Cases

    def login(self, email: str, password: str) -> LoginResult:
        """
            Authenticate a user and issue an access token and a refresh token.

            A disabled account is rejected like a wrong password. If the stored
            hash was created with outdated Argon2 parameters, it is upgraded
            after the successful check.

            Args:
                email: The email address of the user.
                password: The plaintext password.

            Returns:
                The access token, the refresh token and the access token lifetime.

            Raises:
                InvalidCredentialsError: If the email or password is wrong or the
                    account is disabled.
        """
        user = self._users.get_by_email(email)
        stored_hash = user.password_hash if user is not None else _DUMMY_HASH
        password_ok = verify_password(password, stored_hash)
        if user is None or not password_ok or not user.is_active:
            raise InvalidCredentialsError("Invalid email or password")

        if needs_rehash(user.password_hash):
            self._users.set_password_hash(user.user_id, hash_password(password))

        return self._issue_tokens(user, self._clock())

    def refresh(self, refresh_token: str) -> LoginResult:
        """
            Exchange a valid refresh token for a new access token and refresh token.

            The presented token is revoked (rotation), so it can be used only once.
            A token of a disabled or deleted user is rejected.

            Args:
                refresh_token: The plaintext refresh token.

            Returns:
                A new access token, a new refresh token and the access token lifetime.

            Raises:
                InvalidTokenError: If the token is unknown, revoked, expired,
                    belongs to a disabled or missing user, or was revoked by a
                    concurrent request.
        """
        now = self._clock()
        token_hash = hash_refresh_token(refresh_token)
        stored = self._refresh_tokens.get_by_hash(token_hash)
        if (
            stored is None
            or stored.revoked_at is not None
            or _ensure_utc(stored.expires_at) <= now
        ):
            raise InvalidTokenError("Invalid refresh token")

        user = self._users.get_by_id(stored.user_id)
        if user is None or not user.is_active:
            raise InvalidTokenError("Invalid refresh token")

        if not self._refresh_tokens.revoke(token_hash, now):
            raise InvalidTokenError("Invalid refresh token")

        return self._issue_tokens(user, now)

    def logout(self, refresh_token: str) -> None:
        """
            Revoke a refresh token.

            The operation is idempotent: an unknown or already revoked token is
            ignored, so the caller cannot learn whether the token existed.

            Args:
                refresh_token: The plaintext refresh token to revoke.
        """
        self._refresh_tokens.revoke(hash_refresh_token(refresh_token), self._clock())

    #endregion

    #region Internal Helpers

    def _issue_tokens(self, user: User, now: datetime) -> LoginResult:
        """
            Create an access token and store a new refresh token for the user.

            Only the hash of the refresh token is persisted.

            Args:
                user: The authenticated user.
                now: The issue time.

            Returns:
                The access token, the plaintext refresh token and the access
                token lifetime.
        """
        access_token = create_access_token(
            user.user_id, user.role.value, self._settings, now=now
        )
        refresh_token = generate_refresh_token()
        self._refresh_tokens.add(
            RefreshToken(
                user_id=user.user_id,
                token_hash=hash_refresh_token(refresh_token),
                expires_at=now + timedelta(days=self._settings.refresh_token_days),
            )
        )
        return LoginResult(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=self._settings.access_token_minutes * 60,
        )

    #endregion

#endregion