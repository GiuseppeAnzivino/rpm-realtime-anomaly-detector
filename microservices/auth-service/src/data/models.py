"""
DATA ACCESS LAYER (ORM MODELS)
Description: Defines the SQLAlchemy ORM models and the persistent data structure of the Auth-Service microservice.
Responsibility: Maps application entities to database tables, defining column types, constraints, default values, and the set of supported user roles.
Independence: Provides the structural data representation consumed by the repository and business logic layers, without implementing persistence operations or application-level business rules.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
import uuid

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, ForeignKey, String, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


#region Declarative Base

class Base(DeclarativeBase):
    """
    Base declarative class shared by all Auth-Service ORM models.
    Provides the common SQLAlchemy metadata registry used to manage table mappings.
    """

#endregion


#region User Roles

class UserRole(str, Enum):
    """
    Defines the application roles available to authenticated users.
    Inheriting from str allows enum values to be used as strings when required.
    """

    CLINICIAN = "clinician"
    ADMIN = "admin"

#endregion


#region User ORM Model

class User(Base):
    """
    ORM model representing a registered user account and its authentication credentials.

    Column defaults (user_id, is_active, created_at) are applied when the row is
    inserted, so they become available after the session flushes or commits the
    object, rather than immediately upon instantiation.

    The role field is restricted to the values defined by UserRole.
    """

    __tablename__ = "users"

    #region Primary Key

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    #endregion


    #region Account Information

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    full_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    #endregion


    #region Authorization and Account Status

    role: Mapped[UserRole] = mapped_column(
        SAEnum(
            UserRole,
            name="user_role",
            native_enum=False,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    #endregion


    #region Audit Information

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        # Timezone-aware UTC timestamp to ensure consistent storage and comparisons.
        default=lambda: datetime.now(timezone.utc),
    )

    #endregion


    #region Representation

    def __repr__(self) -> str:
        """
        Returns a safe string representation of the user account.

        Sensitive authentication data, such as the password hash, is deliberately
        excluded to prevent accidental exposure in logs and debugging output.

        Returns:
            A string containing the user's identifier, email, role, and account status.
        """
        role_value = self.role.value if self.role is not None else None
        return (
            f"<User(user_id={self.user_id!r}, email={self.email!r}, "
            f"role={role_value!r}, is_active={self.is_active!r})>"
        )

    #endregion

#endregion


#region Refresh Token ORM Model

class RefreshToken(Base):
    """
    ORM model representing a refresh token issued at login.

    Only the SHA-256 hash of the token is stored, never the token itself, so a
    database leak does not expose tokens that can be used. A token is revoked by
    setting revoked_at; rows are deleted together with their user.
    """

    __tablename__ = "refresh_tokens"

    token_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

#endregion