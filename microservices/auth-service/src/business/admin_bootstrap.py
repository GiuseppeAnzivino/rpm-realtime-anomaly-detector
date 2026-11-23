"""
BUSINESS LAYER (ADMIN BOOTSTRAP)
Description: Creates the initial administrator account of the Auth-Service microservice on first startup.
Responsibility: Reads the admin credentials from environment variables, hashes the password and persists the account through the user repository if it does not exist yet.
Independence: Uses only the repository and the security module; it can be invoked from any startup hook.
"""

import logging
import os

from business.exceptions import DuplicateEmailError
from business.security import hash_password
from data.models import User, UserRole
from data.repository import UserRepository, normalise_email

logger = logging.getLogger(__name__)

MIN_PASSWORD_LENGTH = 12
DEFAULT_ADMIN_NAME = "Administrator"


#region Admin Bootstrap

def bootstrap_admin(repository: UserRepository) -> User | None:
    """
        Create the initial admin account if it is not already present.

        Reads ADMIN_EMAIL, ADMIN_PASSWORD and (optionally) ADMIN_FULL_NAME
        from the environment. The operation is idempotent: if a user with the
        configured email already exists, nothing is changed, so the password
        in the environment never overwrites an existing account.

        Args:
            repository: The repository used to look up and persist the user.

        Returns:
            The newly created admin, or ``None`` if the account already existed.

        Raises:
            RuntimeError: If ADMIN_EMAIL or ADMIN_PASSWORD is missing, or if
                the password is shorter than ``MIN_PASSWORD_LENGTH``.
    """
    email = os.environ.get("ADMIN_EMAIL", "").strip()
    password = os.environ.get("ADMIN_PASSWORD", "")
    full_name = os.environ.get("ADMIN_FULL_NAME", "").strip() or DEFAULT_ADMIN_NAME

    if not email or not password:
        raise RuntimeError("ADMIN_EMAIL and ADMIN_PASSWORD must be set")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise RuntimeError(
            f"ADMIN_PASSWORD must be at least {MIN_PASSWORD_LENGTH} characters long"
        )

    if repository.get_by_email(email) is not None:
        logger.info("Admin bootstrap skipped, %s already exists", normalise_email(email))
        return None

    admin = User(
        email=email,
        password_hash=hash_password(password),
        full_name=full_name,
        role=UserRole.ADMIN,
    )
    try:
        created = repository.add(admin)
    except DuplicateEmailError:
        # Another instance created it between the lookup and the insert.
        logger.info("Admin bootstrap skipped, account created concurrently")
        return None

    logger.info("Admin account created: %s", created.email)
    return created

#endregion