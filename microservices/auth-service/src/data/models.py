"""SQLAlchemy ORM models for the authentication service."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
import uuid

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, String, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base declarative class for all auth-service ORM models."""


class UserRole(str, Enum):
    """Allowed application roles for authenticated users."""

    CLINICIAN = "clinician"
    ADMIN = "admin"


class User(Base):
    """ORM model representing a registered user account and credentials.

    Column defaults (user_id, role, is_active, created_at) are applied when the
    row is inserted, so they are available after the session flushes or commits
    the object, and not on a newly instantiated one.
    """

    __tablename__ = "users"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
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
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        # Timezone-aware UTC timestamp so comparisons and storage stay consistent.
        default=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        """Return a safe string representation without sensitive fields."""
        role_value = self.role.value if self.role is not None else None
        return (
            f"<User(user_id={self.user_id!r}, email={self.email!r}, "
            f"role={role_value!r}, is_active={self.is_active!r})>"
        )