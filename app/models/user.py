"""Identity and consent models.

Tables
------
users              Platform accounts (email / password, role, soft-delete).
consent_records    Timestamped, typed consent grants for data processing.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import ConsentType, UserRole


# ---------------------------------------------------------------------------
# Platform accounts
# ---------------------------------------------------------------------------


class User(Base):
    """A platform account.

    ``email`` is stored as plain TEXT in the ORM; the PostgreSQL schema
    uses CITEXT for case-insensitive matching.  ``deleted_at`` supports
    soft-delete: a scheduled purge job removes soft-deleted rows after a
    retention window.
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4,
    )
    # CITEXT on PostgreSQL for case-insensitive uniqueness.
    email: Mapped[str] = mapped_column(String(320), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, name="user_role", create_constraint=True, validate_strings=True),
        default=UserRole.user,
    )
    # MVP gate: users must confirm they are 18+.
    is_adult_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    # Soft-delete timestamp; NULL means active.
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )


# ---------------------------------------------------------------------------
# Consent audit trail
# ---------------------------------------------------------------------------


class ConsentRecord(Base):
    """An auditable record that a user granted (or revoked) a specific consent.

    Each row captures the exact ``version`` of the consent text that was
    displayed, so historical grants remain verifiable even after the
    consent copy is updated.
    """

    __tablename__ = "consent_records"

    __table_args__ = (
        # Composite index for efficient latest-consent lookups.
        # PostgreSQL should add DESC on created_at for recency ordering.
        Index("ix_consent_user_type_date", "user_id", "type", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
    )
    type: Mapped[ConsentType] = mapped_column(
        SAEnum(ConsentType, name="consent_type", create_constraint=True, validate_strings=True),
    )
    # Semantic version of the consent text shown to the user.
    version: Mapped[str] = mapped_column(Text)
    granted: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
