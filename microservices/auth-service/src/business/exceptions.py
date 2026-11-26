"""
BUSINESS LAYER (APPLICATION EXCEPTIONS)
Description: Definition of application-level exceptions for the Auth-Service microservice.
Responsibilities: Centralization of exceptions used by the business logic to represent application errors and exceptional conditions during operation execution.
Independence: Abstraction of errors originating from lower layers, avoiding direct dependencies on persistence-specific implementations.
"""


#region Base business exception

class DataLayerError(Exception):
    """
        Base exception for data-access failures handled by the business layer.

        Provides an abstraction for persistence-related errors, preventing upper
        layers from depending on database or ORM-specific exception types.
    """


#endregion


#region User-related business exceptions

class DuplicateEmailError(DataLayerError):
    """
        Raised when a user cannot be created because the email already exists.

        Represents a conflict caused by an email address that is already
        associated with an existing user.
    """


class UserNotFoundError(DataLayerError):
    """
        Raised when a requested user does not exist.

        Indicates that an operation references a user ID for which no
        corresponding user can be found.
    """


#endregion


#region Authentication-related business exceptions

class AuthenticationError(Exception):
    """
        Base exception for authentication failures.

        Allows the upper layers to handle every authentication error in a single
        place, without listing each specific exception.
    """


class InvalidCredentialsError(AuthenticationError):
    """
        Raised when a login attempt fails.

        The message never reveals whether the email or the password was wrong,
        nor whether the account exists or is disabled.
    """


class InvalidTokenError(AuthenticationError):
    """
        Raised when an access token is malformed, expired, forged or of the wrong type.
    """


#endregion