"""
TEST SUITE (UNIT TESTS)
Description: Contains unit tests for validating the UserRepository implementation and email normalization utility of the Auth-Service microservice.
Responsibility: Verifies user creation, retrieval, updates, deletion, email normalization, duplicate email handling, transaction rollback, database integrity constraints, and behavior when requested users do not exist.
Independence: Uses pytest, SQLAlchemy, and an isolated in-memory SQLite database to test repository operations without requiring an external database instance or other application services.
"""

import uuid
from functools import partial

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from business.exceptions import DuplicateEmailError, UserNotFoundError
from data.models import Base, User, UserRole
from data.repository import UserRepository, normalise_email


#region Test Fixtures

@pytest.fixture(name="session")
def fixture_session():
    """
        Provide a database session backed by an isolated in-memory SQLite database.

        Creates all ORM tables before yielding the session and disposes of the
        database engine after the test completes.

        Yields:
            Session: An active SQLAlchemy session connected to the test database.
    """
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


@pytest.fixture(name="repository")
def fixture_repository(session):
    """
        Provide a UserRepository instance using the test database session.

        Args:
            session: The SQLAlchemy session connected to the in-memory test database.

        Returns:
            UserRepository: The repository configured for the current test.
    """
    return UserRepository(session)


@pytest.fixture(name="make_user")
def fixture_make_user():
    """
        Provide a reusable User constructor with default test account attributes.

        Returns:
            partial: A partially configured User constructor requiring only
                the account-specific fields, such as email.
    """
    return partial(
        User,
        password_hash="not-a-real-hash",
        full_name="Test User",
        role=UserRole.CLINICIAN,
    )


@pytest.fixture(name="created_user")
def fixture_created_user(repository, make_user):
    """
        Provide a user account already persisted through the repository.

        Args:
            repository: The repository used to create the test account.
            make_user: The partially configured User constructor.

        Returns:
            User: The persisted test user with generated fields populated.
    """
    return repository.add(make_user(email="rossi@example.com"))


#endregion


#region Email Normalization Tests

def test_normalise_email_trims_and_lowercases():
    """
        Verify that email normalization removes surrounding whitespace
        and converts uppercase characters to lowercase.

        Asserts:
            The normalized address matches the expected canonical representation.
    """
    assert normalise_email("  Dr.Rossi@Example.COM ") == "dr.rossi@example.com"


#endregion


#region User Creation Tests

def test_add_persists_user_with_generated_fields(created_user):
    """
        Verify that adding a user persists the account and populates
        its automatically generated fields.

        Args:
            created_user: A user account already persisted through the repository.

        Asserts:
            The user has a valid UUID, an active status by default,
            and a non-null creation timestamp.
    """
    assert isinstance(created_user.user_id, uuid.UUID)
    assert created_user.is_active is True
    assert created_user.created_at is not None


def test_add_stores_normalised_email(repository, make_user):
    """
        Verify that the repository normalizes an email before persisting a user.

        Args:
            repository: The repository used to persist the test account.
            make_user: The partially configured User constructor.

        Asserts:
            The stored email contains no surrounding whitespace and
            uses lowercase characters.
    """
    user = repository.add(make_user(email="  Bianchi@Example.COM "))

    assert user.email == "bianchi@example.com"


def test_add_rejects_duplicate_email(repository, session, make_user, created_user):
    """
        Verify that creating a user with an already registered email is rejected.

        Args:
            repository: The repository used to perform the insertion.
            session: The SQLAlchemy session used to inspect database contents.
            make_user: The partially configured User constructor.
            created_user: The existing user whose email is already registered.

        Asserts:
            DuplicateEmailError is raised and the database retains only
            the original user account.
    """
    with pytest.raises(DuplicateEmailError):
        repository.add(make_user(email="rossi@example.com"))

    assert session.scalar(select(func.count()).select_from(User)) == 1


def test_add_rejects_duplicate_email_ignoring_case(repository, make_user, created_user):
    """
        Verify that duplicate email detection is case-insensitive.

        Args:
            repository: The repository used to perform the insertion.
            make_user: The partially configured User constructor.
            created_user: The existing user whose email is already registered.

        Asserts:
            An email matching an existing address after normalization
            raises DuplicateEmailError.
    """
    with pytest.raises(DuplicateEmailError):
        repository.add(make_user(email="ROSSI@example.com"))


def test_add_reraises_other_integrity_errors(repository, make_user):
    """
        Verify that integrity violations unrelated to duplicate emails
        are propagated as SQLAlchemy IntegrityError exceptions.

        Args:
            repository: The repository used to perform the insertion.
            make_user: The partially configured User constructor.

        Asserts:
            An insertion violating the non-nullable role constraint
            raises IntegrityError rather than DuplicateEmailError.
    """
    with pytest.raises(IntegrityError):
        repository.add(make_user(email="verdi@example.com", role=None))


def test_repository_stays_usable_after_a_failed_add(repository, make_user, created_user):
    """
        Verify that the repository remains usable after a failed insertion.

        Args:
            repository: The repository used to perform both insertions.
            make_user: The partially configured User constructor.
            created_user: The existing user whose email causes the first insertion to fail.

        Asserts:
            After the duplicate email error, a subsequent valid insertion
            succeeds and the new account is persisted correctly.
    """
    with pytest.raises(DuplicateEmailError):
        repository.add(make_user(email="rossi@example.com"))

    created = repository.add(make_user(email="bianchi@example.com"))

    assert created.email == "bianchi@example.com"


#endregion


#region User Retrieval Tests

def test_get_by_id_returns_the_user(repository, created_user):
    """
        Verify that an existing user can be retrieved by its UUID.

        Args:
            repository: The repository used to retrieve the account.
            created_user: The existing persisted user.

        Asserts:
            The returned object is the same user instance already present
            in the current SQLAlchemy session.
    """
    assert repository.get_by_id(created_user.user_id) is created_user


def test_get_by_id_returns_none_for_unknown_id(repository):
    """
        Verify that retrieving a nonexistent user identifier returns None.

        Args:
            repository: The repository used to perform the lookup.

        Asserts:
            The lookup returns None when no matching user exists.
    """
    assert repository.get_by_id(uuid.uuid4()) is None


def test_get_by_email_ignores_case_and_whitespace(repository, created_user):
    """
        Verify that email-based retrieval ignores capitalization
        and surrounding whitespace.

        Args:
            repository: The repository used to perform the lookup.
            created_user: The existing persisted user.

        Asserts:
            The normalized lookup resolves to the existing user account.
    """
    assert repository.get_by_email(" ROSSI@example.com ") is created_user


def test_get_by_email_returns_none_for_unknown_email(repository):
    """
        Verify that retrieving a nonexistent email address returns None.

        Args:
            repository: The repository used to perform the lookup.

        Asserts:
            The lookup returns None when no matching email exists.
    """
    assert repository.get_by_email("nobody@example.com") is None


#endregion


#region User Update Tests

def test_set_email_stores_the_normalised_email(repository, created_user):
    """
        Verify that updating a user's email stores its normalized representation.

        Args:
            repository: The repository used to update and retrieve the account.
            created_user: The existing persisted user.

        Asserts:
            The updated address is normalized, the new address resolves
            to the user, and the previous address no longer matches.
    """
    updated = repository.set_email(created_user.user_id, "  New.Rossi@Example.COM ")

    assert updated.email == "new.rossi@example.com"
    assert repository.get_by_email("new.rossi@example.com") is updated
    assert repository.get_by_email("rossi@example.com") is None


def test_set_email_accepts_the_users_own_email(repository, created_user):
    """
        Verify that a user can retain their own email address without triggering
        a duplicate email error.

        Args:
            repository: The repository used to update the account.
            created_user: The existing persisted user.

        Asserts:
            The operation succeeds and stores the normalized email address.
    """
    updated = repository.set_email(created_user.user_id, "ROSSI@example.com")

    assert updated.email == "rossi@example.com"


def test_set_email_rejects_an_email_used_by_another_user(
    repository, make_user, created_user
):
    """
        Verify that an email address already assigned to another user
        cannot be reused during an update.

        Args:
            repository: The repository used to perform the update.
            make_user: The partially configured User constructor.
            created_user: The existing user whose email must remain unchanged.

        Asserts:
            DuplicateEmailError is raised and the second user's original
            email address is preserved.
    """
    other = repository.add(make_user(email="bianchi@example.com"))

    with pytest.raises(DuplicateEmailError):
        repository.set_email(other.user_id, "Rossi@example.com")

    assert repository.get_by_id(other.user_id).email == "bianchi@example.com"


def test_set_full_name_updates_the_user(repository, created_user):
    """
        Verify that the repository updates an existing user's full name.

        Args:
            repository: The repository used to perform the update.
            created_user: The existing persisted user.

        Asserts:
            The returned user contains the newly assigned full name.
    """
    updated = repository.set_full_name(created_user.user_id, "Mario Rossi")

    assert updated.full_name == "Mario Rossi"


def test_set_role_updates_the_user(repository, created_user):
    """
        Verify that the repository updates an existing user's application role.

        Args:
            repository: The repository used to perform the update.
            created_user: The existing persisted user.

        Asserts:
            The returned user has the ADMIN role after the update.
    """
    updated = repository.set_role(created_user.user_id, UserRole.ADMIN)

    assert updated.role is UserRole.ADMIN


def test_set_active_disables_and_enables_the_user(repository, created_user):
    """
        Verify that the repository can both disable and re-enable a user account.

        Args:
            repository: The repository used to perform the updates.
            created_user: The existing persisted user.

        Asserts:
            The account status reflects each successive update.
    """
    disabled = repository.set_active(created_user.user_id, False)
    assert disabled.is_active is False

    enabled = repository.set_active(created_user.user_id, True)
    assert enabled.is_active is True


def test_set_password_hash_replaces_the_hash(repository, created_user):
    """
        Verify that the repository replaces an existing user's password hash.

        Args:
            repository: The repository used to perform the update.
            created_user: The existing persisted user.

        Asserts:
            The returned user contains the newly assigned password hash.
    """
    updated = repository.set_password_hash(created_user.user_id, "another-hash")

    assert updated.password_hash == "another-hash"


def test_setter_reraises_other_integrity_errors(repository, created_user):
    """
        Verify that attribute updates propagate integrity errors unrelated
        to duplicate email addresses.

        Args:
            repository: The repository used to perform the update.
            created_user: The existing persisted user.

        Asserts:
            Setting a non-nullable full name to None raises IntegrityError
            and the previous persisted value remains unchanged after rollback.
    """
    with pytest.raises(IntegrityError):
        repository.set_full_name(created_user.user_id, None)

    assert repository.get_by_id(created_user.user_id).full_name == "Test User"


#endregion


#region Missing User Handling Tests

@pytest.mark.parametrize(
    "method, value",
    [
        ("set_email", "someone@example.com"),
        ("set_full_name", "Someone"),
        ("set_role", UserRole.ADMIN),
        ("set_active", False),
        ("set_password_hash", "a-hash"),
    ],
)
def test_setters_raise_for_unknown_user(repository, method, value):
    """
        Verify that all user update methods reject nonexistent user identifiers.

        Args:
            repository: The repository used to perform the update.
            method: The name of the update method to invoke.
            value: The replacement value passed to the selected method.

        Asserts:
            Every parametrized update operation raises UserNotFoundError
            when the specified user identifier does not exist.
    """
    with pytest.raises(UserNotFoundError):
        getattr(repository, method)(uuid.uuid4(), value)


#endregion


#region User Deletion Tests

def test_remove_deletes_the_user(repository, session, created_user):
    """
        Verify that removing an existing user permanently deletes its database record.

        Args:
            repository: The repository used to delete the account.
            session: The SQLAlchemy session used to inspect database contents.
            created_user: The existing persisted user to delete.

        Asserts:
            No user records remain in the database after deletion.
    """
    repository.remove(created_user.user_id)

    assert session.scalar(select(func.count()).select_from(User)) == 0


def test_remove_raises_for_unknown_user(repository):
    """
        Verify that attempting to remove a nonexistent user raises an application error.

        Args:
            repository: The repository used to perform the deletion.

        Asserts:
            UserNotFoundError is raised when the specified identifier
            does not match any existing user.
    """
    with pytest.raises(UserNotFoundError):
        repository.remove(uuid.uuid4())


#endregion