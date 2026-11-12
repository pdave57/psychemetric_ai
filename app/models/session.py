"""Assessment session and response-capture models.

Tables
------
assessment_sessions    A user's attempt at completing an instrument version.
user_responses         Individual answers submitted during a session.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import SessionStatus


# ---------------------------------------------------------------------------
# Session tracking
# ---------------------------------------------------------------------------


class AssessmentSession(Base):
    """One user's attempt at completing an assessment instrument.

    Each session pins an exact instrument version (``version_id``) so
    that scoring and report generation always reference the content the
    user actually saw.

    Status transitions::

        in_progress → completed
        in_progress → safety_paused → in_progress  (safety review loop)
        in_progress → abandoned

    ``graph_thread_id`` is reserved for LangGraph checkpoint threading
    to support session resume in a later milestone.
    """

    __tablename__ = "assessment_sessions"

    __table_args__ = (
        # Composite index for efficient per-user session listing.
        Index("ix_session_user_started", "user_id", "started_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4,
    )
    # Opaque user identifier — stored as text until auth is implemented.
    # FK to users.id is enforced at migration time, not via SQLAlchemy ForeignKey
    # here, so that the prototype can run without a users row.
    user_id: Mapped[str] = mapped_column(String(320), index=True)
    version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assessment_versions.id"),
    )
    status: Mapped[SessionStatus] = mapped_column(
        SAEnum(
            SessionStatus,
            name="session_status",
            create_constraint=True,
            validate_strings=True,
        ),
        default=SessionStatus.in_progress,
    )
    # LangGraph checkpoint thread for session resume (nullable until implemented).
    graph_thread_id: Mapped[str | None] = mapped_column(
        Text, unique=True, nullable=True,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    # Updated on every interaction to detect abandoned sessions.
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# User answers
# ---------------------------------------------------------------------------


class UserResponse(Base):
    """A single answer submitted by a user during an assessment session.

    Forced-choice responses store ``option_id`` (FK → question_options).
    Likert responses store ``likert_value`` (1–5 integer).  Both may
    coexist when a Likert item also presents named options.

    ``is_unsure`` is set when the user selected the "I'm not sure"
    option.  ``free_text_enc`` holds optional encrypted free-text that
    the user volunteered (encryption is application-level, not DB-level).

    The ``uq_session_question`` constraint ensures at most one response
    per question per session; the ``uq_session_seq`` constraint ensures
    ordering integrity.
    """

    __tablename__ = "user_responses"

    __table_args__ = (
        UniqueConstraint("session_id", "question_id", name="uq_session_question"),
        UniqueConstraint("session_id", "seq", name="uq_session_seq"),
        CheckConstraint("likert_value BETWEEN 1 AND 5", name="ck_likert_range"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4,
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assessment_sessions.id", ondelete="CASCADE"),
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("questions.id"),
    )
    # FK to the selected option (for forced-choice items).
    option_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("question_options.id"), nullable=True,
    )
    # Likert scale value (1–5); NULL for pure forced-choice items.
    likert_value: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    # Whether the user selected the "I'm not sure" escape hatch.
    is_unsure: Mapped[bool] = mapped_column(Boolean, default=False)
    # Application-level encrypted free-text (BYTEA on PostgreSQL).
    free_text_enc: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    # Sequence number: the order in which items were presented / answered.
    seq: Mapped[int] = mapped_column(Integer)
    answered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
