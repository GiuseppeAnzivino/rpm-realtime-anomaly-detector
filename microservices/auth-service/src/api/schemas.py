"""
PRESENTATION LAYER (AUTHENTICATION SCHEMAS)
Description: Request and response models of the authentication endpoints of the Auth-Service microservice.
Responsibility: Defines and validates the JSON bodies of login and logout.
Independence: Depends only on Pydantic.
"""

from pydantic import BaseModel, Field


#region Request Models

class LoginRequest(BaseModel):
    """The credentials sent to the login endpoint."""

    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=128)


class LogoutRequest(BaseModel):
    """The refresh token sent to the logout endpoint."""

    refresh_token: str = Field(min_length=1)

#endregion


#region Response Models

class TokenResponse(BaseModel):
    """The tokens returned by a successful login."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int

#endregion