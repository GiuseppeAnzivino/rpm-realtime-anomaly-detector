"""
TEST SUITE (UNIT TESTS)
Description: Contains unit tests for verifying the application exception hierarchy of the Auth-Service microservice.
Responsibility: Ensures that specific exceptions correctly inherit from DataLayerError, that DataLayerError derives from the built-in Exception class, and that custom exception messages are preserved.
Independence: Uses pytest to validate exception behavior without requiring database interactions or dependencies on other application components.
"""

import pytest

from business.exceptions import DataLayerError, DuplicateEmailError, UserNotFoundError


#region Exception Hierarchy Tests

@pytest.mark.parametrize("error_class", [DuplicateEmailError, UserNotFoundError])
def test_specific_errors_are_data_layer_errors(error_class):
    """
        Verify that specific persistence exceptions inherit from DataLayerError.

        Args:
            error_class: The exception class whose inheritance is being checked.

        Asserts:
            The specified exception class is a subclass of DataLayerError.
    """
    assert issubclass(error_class, DataLayerError)


def test_data_layer_error_is_an_exception():
    """
        Verify that DataLayerError inherits from the built-in Exception class.

        Asserts:
            DataLayerError is a subclass of Exception.
    """
    assert issubclass(DataLayerError, Exception)


#endregion


#region Exception Message Tests

def test_errors_keep_their_message():
    """
        Verify that custom exception messages are preserved upon instantiation.

        Asserts:
            The string representation of UserNotFoundError matches the
            message provided during instantiation.
    """
    error = UserNotFoundError("No user with id 42")

    assert str(error) == "No user with id 42"


#endregion