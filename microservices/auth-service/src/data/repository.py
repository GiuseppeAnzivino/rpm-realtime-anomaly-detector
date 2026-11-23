"""
DATA ACCESS LAYER (REPOSITORY)
Description: Implements the Repository pattern for managing user accounts in the Auth-Service microservice.
Responsibility: Handles persistence operations on User entities through SQLAlchemy, including creation, retrieval, updates, and deletion.
Independence: Encapsulates database access and translates data integrity violations into application-level exceptions, preventing the business logic layer from depending directly on persistence details.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from business.exceptions import DuplicateEmailError, UserNotFoundError
from data.models import User, UserRole


#region Email Normalization

def normalise_email(email: str) -> str:
    """
        Return the canonical form of an email address by trimming whitespace
        and converting all characters to lowercase.

        This ensures that addresses differing only in capitalization or
        surrounding whitespace are treated as the same account.

        Args:
            email: The email address to normalize.

        Returns:
            The normalized email address.
    """
    return email.strip().lower()


#endregion


#region User Repository

class UserRepository:
    """
        Encapsulates persistence operations for User accounts.

        The repository operates on a SQLAlchemy session provided by the caller
        and commits each write operation individually. Failed transactions are
        rolled back to restore the session to a usable state.

        Operations requiring an existing user raise ``UserNotFoundError``
        when the specified identifier does not match any record.
    """

    def __init__(self, session: Session) -> None:
        """
            Initialize the repository with a SQLAlchemy session.

            Args:
                session: The database session used for persistence operations.
        """
        self._session = session

    #region User Creation and Deletion

    def add(self, user: User) -> User:
        """
            Persist a new user account and return it with generated fields populated.

            The email address is normalized before insertion. The session is
            committed and the entity refreshed to retrieve database-generated
            or default values.

            Args:
                user: The user entity to persist.

            Returns:
                The persisted user with its generated fields populated.

            Raises:
                DuplicateEmailError: If the email is already registered.
                IntegrityError: If another database constraint is violated.
        """
        user.email = normalise_email(user.email)
        self._session.add(user)
        self._commit(email=user.email)
        self._session.refresh(user)
        return user

    def remove(self, user_id: uuid.UUID) -> None:
        """
            Permanently delete an existing user account.

            Args:
                user_id: The unique identifier of the user to delete.

            Raises:
                UserNotFoundError: If the user does not exist.
                IntegrityError: If a database constraint prevents deletion.
        """
        user = self._require(user_id)
        self._session.delete(user)
        self._session.commit()

    #endregion

    #region User Retrieval

    def get_by_id(self, user_id: uuid.UUID) -> User | None:
        """
            Retrieve a user by its primary key.

            Args:
                user_id: The unique identifier of the user.

            Returns:
                The matching user, or ``None`` if no user exists.
        """
        return self._session.get(User, user_id)

    def get_by_email(self, email: str) -> User | None:
        """
            Retrieve a user by email address.

            The lookup is case-insensitive and ignores surrounding whitespace
            by normalizing the input before querying the database.

            Args:
                email: The email address used to identify the user.

            Returns:
                The matching user, or ``None`` if no user exists.
        """
        statement = select(User).where(User.email == normalise_email(email))
        return self._session.scalar(statement)

    #endregion

    #region User Updates

    def set_email(self, user_id: uuid.UUID, email: str) -> User:
        """
            Change the email address of an existing user.

            The new address is normalized before assignment and persistence.

            Args:
                user_id: The unique identifier of the user to update.
                email: The new email address.

            Returns:
                The updated user.

            Raises:
                UserNotFoundError: If the user does not exist.
                DuplicateEmailError: If another user already has that email.
                IntegrityError: If another database constraint is violated.
        """
        user = self._require(user_id)
        new_email = normalise_email(email)
        user.email = new_email
        self._commit(email=new_email)
        return user

    def set_full_name(self, user_id: uuid.UUID, full_name: str) -> User:
        """
            Update the full name of an existing user.

            Args:
                user_id: The unique identifier of the user to update.
                full_name: The new full name.

            Returns:
                The updated user.

            Raises:
                UserNotFoundError: If the user does not exist.
                IntegrityError: If a database constraint is violated.
        """
        return self._set_attribute(user_id, "full_name", full_name)

    def set_role(self, user_id: uuid.UUID, role: UserRole) -> User:
        """
            Update the application role assigned to an existing user.

            Args:
                user_id: The unique identifier of the user to update.
                role: The new user role.

            Returns:
                The updated user.

            Raises:
                UserNotFoundError: If the user does not exist.
                IntegrityError: If a database constraint is violated.
        """
        return self._set_attribute(user_id, "role", role)

    def set_active(self, user_id: uuid.UUID, is_active: bool) -> User:
        """
            Enable or disable an existing user account without deleting it.

            Args:
                user_id: The unique identifier of the user to update.
                is_active: Whether the account should be active.

            Returns:
                The updated user.

            Raises:
                UserNotFoundError: If the user does not exist.
                IntegrityError: If a database constraint is violated.
        """
        return self._set_attribute(user_id, "is_active", is_active)

    def set_password_hash(self, user_id: uuid.UUID, password_hash: str) -> User:
        """
            Replace the stored password hash of an existing user.

            The supplied value must already be hashed. Password hashing is
            performed by the business logic layer, not by the repository.

            Args:
                user_id: The unique identifier of the user to update.
                password_hash: The precomputed password hash to store.

            Returns:
                The updated user.

            Raises:
                UserNotFoundError: If the user does not exist.
                IntegrityError: If a database constraint is violated.
        """
        return self._set_attribute(user_id, "password_hash", password_hash)

    #endregion

    #region Internal Repository Helpers

    def _require(self, user_id: uuid.UUID) -> User:
        """
            Retrieve an existing user or raise ``UserNotFoundError``.

            Centralizes the existence check used by repository operations
            that require a valid user record.

            Args:
                user_id: The unique identifier of the user to retrieve.

            Returns:
                The matching user.

            Raises:
                UserNotFoundError: If no user exists with the given identifier.
        """
        user = self.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError(f"No user with id {user_id}")
        return user

    def _set_attribute(self, user_id: uuid.UUID, name: str, value: object) -> User:
        """
            Update a single user attribute and persist the change.

            Provides a shared implementation for simple field updates,
            avoiding duplicated retrieval, assignment, and commit operations.

            Args:
                user_id: The unique identifier of the user to update.
                name: The name of the attribute to modify.
                value: The new value to assign to the attribute.

            Returns:
                The updated user.

            Raises:
                UserNotFoundError: If the user does not exist.
                IntegrityError: If a database constraint is violated.
        """
        user = self._require(user_id)
        setattr(user, name, value)
        self._commit()
        return user

    def _commit(self, email: str | None = None) -> None:
        """
            Commit the current transaction and translate duplicate email violations.

            On an integrity error, the transaction is rolled back before
            checking whether the email is already associated with another user.
            If a duplicate is identified, the database exception is translated
            into the corresponding application-level exception.

            Args:
                email: The email address involved in the write operation, if any.
                    Used to distinguish duplicate email violations from other
                    database integrity errors.

            Raises:
                DuplicateEmailError: If the email already belongs to another user.
                IntegrityError: If another database constraint is violated.
        """
        try:
            self._session.commit()
        except IntegrityError as error:
            self._session.rollback()
            if email is not None and self.get_by_email(email) is not None:
                raise DuplicateEmailError(
                    "A user with this email already exists"
                ) from error
            raise

    #endregion

#endregion