"""
BUSINESS LAYER (AUTHENTICATION SERVICE)
Description: Login logic of the Auth-Service microservice.
Responsibility: Verifies the credentials of a user and issues a JWT access token.
Independence: Uses only the user repository, the password module and the token module; it knows nothing about HTTP.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone

from business.exceptions import InvalidCredentialsError
from business.security import hash_password, needs_rehash, verify_password
from business.tokens import TokenSettings, create_access_token
from data.repository import UserRepository

# Verified when the user does not exist, so that "unknown email" and
# "wrong password" take the same time and the response does not reveal
# which emails are registered.
_DUMMY_HASH = hash_password("dummy-password")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


#region Login Result

@dataclass(frozen=True)
class LoginResult:
    """
        The outcome of a successful login.

        Attributes:
            access_token: The signed JWT.
            expires_in: Lifetime of the access token, in seconds.
    """

    access_token: str
    expires_in: int

#endregion


#region Authentication Service

class AuthService:
    """
        Implements the login use case.

        The clock is injectable so that tests control the issue and expiry times.
    """

    def __init__(
        self,
        users: UserRepository,
        settings: TokenSettings,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        """
            Initialize the service.

            Args:
                users: The repository used to look up users.
                settings: The token settings.
                clock: A function returning the current UTC time.
        """
        self._users = users
        self._settings = settings
        self._clock = clock

    def login(self, email: str, password: str) -> LoginResult:
        """
            Authenticate a user and issue an access token.

            A disabled account is rejected like a wrong password. If the stored
            hash was created with outdated Argon2 parameters, it is upgraded
            after the successful check.

            Args:
                email: The email address of the user.
                password: The plaintext password.

            Returns:
                The access token and its lifetime.

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

        access_token = create_access_token(
            user.user_id, user.role.value, self._settings, now=self._clock()
        )
        return LoginResult(
            access_token=access_token,
            expires_in=self._settings.access_token_minutes * 60,
        )

#endregion