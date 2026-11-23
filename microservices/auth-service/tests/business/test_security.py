"""
TEST SUITE (UNIT TESTS)
    Description: Contains unit tests for validating the password hashing, verification, and rehash detection utilities of the Auth-Service microservice.
    Responsibility: Verifies Argon2id password hashing, salt uniqueness, password verification, malformed hash handling, empty password rejection, and rehash detection.
    Independence: Tests the security utilities directly without requiring a database, application server, or other external services.
"""

import pytest

from business.security import hash_password, needs_rehash, verify_password


#region Password Hashing Tests

def test_hash_is_not_plaintext_and_is_argon2id():
    """
        Verify that passwords are stored as Argon2id hashes rather than plaintext.

        Asserts:
            The generated hash differs from the original password and
            uses the expected Argon2id algorithm identifier.
    """
    hashed = hash_password("correct horse battery")
    assert hashed != "correct horse battery"
    assert hashed.startswith("$argon2id$")


def test_same_password_produces_different_hashes():
    """
        Verify that hashing the same password multiple times produces different hashes.

        Asserts:
            Each generated hash is unique due to the use of randomly generated salts.
    """
    assert hash_password("same-password-1") != hash_password("same-password-1")


def test_hash_rejects_empty_password():
    """
        Verify that password hashing rejects empty input.

        Asserts:
            Hashing an empty password raises a ValueError.
    """
    with pytest.raises(ValueError):
        hash_password("")


#endregion


#region Password Verification Tests

def test_verify_accepts_correct_password():
    """
        Verify that password verification accepts the original password.

        Asserts:
            The verification function returns True when the supplied password
            matches the stored hash.
    """
    hashed = hash_password("s3cret-passphrase")
    assert verify_password("s3cret-passphrase", hashed) is True


def test_verify_rejects_wrong_password():
    """
        Verify that password verification rejects an incorrect password.

        Asserts:
            The verification function returns False when the supplied password
            does not match the stored hash.
    """
    hashed = hash_password("s3cret-passphrase")
    assert verify_password("wrong", hashed) is False


def test_verify_returns_false_on_malformed_hash():
    """
        Verify that malformed password hashes are handled safely.

        Asserts:
            The verification function returns False instead of raising an
            exception when the stored hash has an invalid format.
    """
    assert verify_password("anything", "not-a-hash") is False


#endregion


#region Password Rehash Tests

def test_needs_rehash_false_for_fresh_hash():
    """
        Verify that a newly generated password hash does not require rehashing.

        Asserts:
            The rehash detection function returns False when the hash
            already complies with the current hashing configuration.
    """
    assert needs_rehash(hash_password("s3cret-passphrase")) is False


#endregion