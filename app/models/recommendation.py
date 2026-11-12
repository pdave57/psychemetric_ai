"""Recommendation engine models.

Tables
------
recommendation_templates    Reusable, rule-driven recommendation content.
recommendations             Personalised recommendations surfaced to a user.
recommendation_history      Audit trail for status changes and feedback.
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
    JSON,
    LargeBinary,
    SmallInteger,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import EvidenceLevel, RecStatus


# ---------------------------------------------------------------------------
# Recommendation templates
# ---------------------------------------------------------------------------


class RecommendationTemplate(Base):
    """A reusable recommendation backed by evidence and matching rules.

    ``id`` is a human-readable slug (e.g. ``rec_pause_ground``) so it
    can be referenced directly in seed data and rules without looking up
    a UUID.

    ``body`` contains structured content:
        why / what / how[] / measure / professional_support_when

    ``rules`` defines the matching criteria:
        min_band / trigger_any / response_any

    ``source_chunk_ids`` links the template to knowledge-base chunks
    that support its content (stored as a JSON array of UUID strings
    for cross-database compatibility).
    """

    __tablename__ = "recommendation_templates"

    # Text slug PK: human-readable and stable across environments.
    id: Mapped[str] = mapped_column(Text, primary_key=True)
    # Emotion this recommendation targets, e.g. "anxiety".
    emotion: Mapped[str] = mapped_column(Text)
    # Short display title.
    title: Mapped[str] = mapped_column(Text)
    # Structured body: why / what / how[] / measure / professional_support_when.
    body: Mapped[dict] = mapped_column(JSON)
    # Matching rules: min_band / trigger_any / response_any.
    rules: Mapped[dict] = mapped_column(JSON)
    evidence: Mapped[EvidenceLevel] = mapped_column(
        SAEnum(
            EvidenceLevel,
            name="evidence_level",
            create_constraint=True,
            validate_strings=True,
        ),
        default=EvidenceLevel.unreviewed_seed,
    )
    # JSON array of knowledge_chunk UUID strings supporting this template.
    source_chunk_ids: Mapped[list] = mapped_column(JSON, default=list)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


# ---------------------------------------------------------------------------
# Personalised recommendations
# ---------------------------------------------------------------------------


class Recommendation(Base):
    """A personalised recommendation generated for a user after a session.

    ``rationale`` is a JSON record of the emotion / trigger evidence
    that caused this template to be matched, enabling auditability and
    future model evaluation.
    """

    __tablename__ = "recommendations"

    __table_args__ = (
        Index("ix_rec_user_status", "user_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assessment_sessions.id", ondelete="CASCADE"),
    )
    template_id: Mapped[str] = mapped_column(
        ForeignKey("recommendation_templates.id"),
    )
    # Emotion and trigger evidence that matched this recommendation.
    rationale: Mapped[dict] = mapped_column(JSON)
    status: Mapped[RecStatus] = mapped_column(
        SAEnum(RecStatus, name="rec_status", create_constraint=True, validate_strings=True),
        default=RecStatus.suggested,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# Recommendation interaction history
# ---------------------------------------------------------------------------


class RecommendationHistory(Base):
    """Audit trail for status changes and user feedback on a recommendation.

    ``event`` type controls which optional fields are relevant:
      * ``status_change`` — ``status`` is set.
      * ``check_in``      — ``helpfulness`` may be set.
      * ``feedback``      — ``outcome_rating`` and ``note_enc`` may be set.

    ``note_enc`` is application-level encrypted to protect free-text
    feedback content.
    """

    __tablename__ = "recommendation_history"

    __table_args__ = (
        CheckConstraint(
            "event IN ('status_change', 'check_in', 'feedback')",
            name="ck_history_event",
        ),
        CheckConstraint("helpfulness BETWEEN 1 AND 5", name="ck_helpfulness_range"),
        CheckConstraint("outcome_rating BETWEEN 0 AND 10", name="ck_outcome_range"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4,
    )
    recommendation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("recommendations.id", ondelete="CASCADE"),
    )
    # "status_change" | "check_in" | "feedback".
    event: Mapped[str] = mapped_column(Text)
    # New status (for status_change events).
    status: Mapped[RecStatus | None] = mapped_column(
        SAEnum(RecStatus, name="rec_status", create_constraint=False, validate_strings=True),
        nullable=True,
    )
    # User-rated helpfulness 1–5 (for check_in events).
    helpfulness: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    # Self-reported outcome rating 0–10 (for feedback events).
    outcome_rating: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    # Application-level encrypted free-text note (optional).
    note_enc: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
