"""Safety monitoring and audit-log models.

Tables
------
safety_events    Flagged safety incidents detected during a session.
audit_log        Append-only log of sensitive data-access actions.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    JSON,
    LargeBinary,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import SafetyLevel


# ---------------------------------------------------------------------------
# Safety events
# ---------------------------------------------------------------------------


class SafetyEvent(Base):
    """A safety-flagged incident detected during an assessment session.

    ``level``      — severity: ``high`` or ``critical``.
    ``categories`` — list of safety category codes (stored as JSON for
                     cross-database compatibility; PostgreSQL schema uses TEXT[]).
    ``detector``   — which detection mechanism raised the flag.
    ``question_id``— the question that triggered the flag (nullable).
    ``raw_text_enc``— application-level encrypted raw text, stored
                      ONLY when the user has granted consent for safety review.
    ``reviewed_by``— staff user who reviewed this event (nullable until reviewed).
    """

    __tablename__ = "safety_events"

    __table_args__ = (
        CheckConstraint(
            "detector IN ('rules', 'llm_classifier', 'user_reported')",
            name="ck_safety_detector",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4,
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assessment_sessions.id", ondelete="CASCADE"),
    )
    level: Mapped[SafetyLevel] = mapped_column(
        SAEnum(SafetyLevel, name="safety_level", create_constraint=True, validate_strings=True),
    )
    # Safety category codes — JSON list for cross-DB compat (TEXT[] in PostgreSQL).
    categories: Mapped[list] = mapped_column(JSON)
    # Detection mechanism: "rules" | "llm_classifier" | "user_reported".
    detector: Mapped[str] = mapped_column(Text)
    # Question that triggered the flag (nullable).
    question_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("questions.id"), nullable=True,
    )
    # Application-level encrypted raw text (stored only with consent).
    raw_text_enc: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    # Staff user who reviewed this event.
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------


class AuditLog(Base):
    """Append-only log of sensitive data-access and mutation actions.

    Rows are never updated or deleted (retention enforced at the DB level
    or via a separate archival process).  ``actor_id`` is nullable to
    handle system-generated events.

    Example ``action`` values: ``report.view``, ``data.export``,
    ``data.delete``.

    Response content is never logged here — only metadata.
    """

    __tablename__ = "audit_log"

    # BIGSERIAL for high-volume append performance (not UUID).
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # The user who performed the action (nullable for system events).
    actor_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    # Action identifier, e.g. "report.view", "data.export".
    action: Mapped[str] = mapped_column(Text)
    # Type of the object the action targeted, e.g. "AssessmentReport".
    object_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    # String representation of the target object's ID.
    object_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Never log response content — only metadata.
    at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
