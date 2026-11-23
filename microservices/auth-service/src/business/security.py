"""
BUSINESS LAYER (PASSWORD SECURITY)
Description: Password hashing and verification for the Auth-Service microservice using Argon2id.
Responsibility: Converts plaintext passwords into salted hashes, verifies candidates against stored hashes, and detects hashes that need to be upgraded.
Independence: Depends only on the argon2-cffi library; it knows nothing about users, persistence, or HTTP.
"""

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

#region Hasher Configuration

# Argon2id with the library's recommended (RFC 9106 low-memory) defaults.
# A random salt is generated automatically for every hash and is embedded
# in the output string together with the algorithm parameters.
_hasher = PasswordHasher()

#endregion


#region Password Hashing

def hash_password(password: str) -> str:
    """
        Hash a plaintext password with Argon2id.

        Args:
            password: The plaintext password to hash.

        Returns:
            The encoded hash, containing algorithm, parameters, salt and digest.

        Raises:
            ValueError: If the password is empty.
    """
    if not password:
        raise ValueError("Password must not be empty")
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """
        Check a plaintext password against a stored hash.

        Never raises for a wrong password or a malformed hash: both simply
        return ``False`` so callers cannot leak information through exceptions.

        Args:
            password: The plaintext password supplied by the user.
            password_hash: The stored hash to compare against.

        Returns:
            ``True`` if the password matches the hash, ``False`` otherwise.
    """
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    """
        Report whether a stored hash was created with outdated parameters.

        Allows transparently upgrading hashes after a successful login when
        the Argon2 parameters are strengthened in the future.

        Args:
            password_hash: The stored hash to inspect.

        Returns:
            ``True`` if the hash should be recomputed, ``False`` otherwise.
    """
    return _hasher.check_needs_rehash(password_hash)

#endregion