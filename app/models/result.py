"""Scoring results, emotional self-reports, and report snapshots.

Tables
------
temperament_scores      Per-dimension scores for a completed session.
emotion_assessments     User self-reported emotional state entries.
emotional_triggers      Trigger codes linked to an emotion assessment.
assessment_reports      Immutable JSON snapshot of a session's full results.
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    SmallInteger,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import EmotionBand


# ---------------------------------------------------------------------------
# Temperament scores
# ---------------------------------------------------------------------------


class TemperamentScore(Base):
    """Computed score for one dimension within a completed session.

    One row per (session, dimension) is enforced by ``uq_session_dimension``.

    ``score``      — 0–100 normalised score (NULL if no items answered).
    ``sem``        — standard error of measurement (NULL if not estimable).
    ``n_items``    — number of items that contributed to the score.
    ``n_areas``    — number of distinct behavioural areas covered.
    ``consistency``— internal-consistency coefficient (Cronbach/split-half).
    ``confidence`` — scoring-engine confidence in [0, 1].
    """

    __tablename__ = "temperament_scores"

    __table_args__ = (
        UniqueConstraint("session_id", "dimension", name="uq_session_dimension"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4,
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assessment_sessions.id", ondelete="CASCADE"),
    )
    # Dimension name, e.g. "sanguine", "choleric".
    dimension: Mapped[str] = mapped_column(Text)
    # Normalised 0–100 score; NULL when too few items answered.
    score: Mapped[Decimal | None] = mapped_column(Numeric(5, 1), nullable=True)
    # Standard error of measurement.
    sem: Mapped[Decimal | None] = mapped_column(Numeric(5, 1), nullable=True)
    # Number of items that contributed to the score.
    n_items: Mapped[int] = mapped_column(Integer)
    # Number of distinct behavioural areas covered by those items.
    n_areas: Mapped[int] = mapped_column(Integer)
    # Internal-consistency estimate (e.g. Cronbach's alpha).
    consistency: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    # Scoring-engine confidence in [0, 1].
    confidence: Mapped[Decimal] = mapped_column(Numeric(4, 3))


# ---------------------------------------------------------------------------
# Emotional self-assessments
# ---------------------------------------------------------------------------


class EmotionAssessment(Base):
    """A user's self-reported emotional state linked to a session.

    All fields are user self-reports; the system does not infer or
    diagnose emotional conditions.  ``burden_index`` is computed by the
    application from frequency × intensity × duration factors.
    ``band`` is derived from ``burden_index`` for recommendation routing.

    ``source`` distinguishes structured form submissions from emotions
    extracted from optional free-text via an NLP step.

    One row per (session, emotion) is enforced by ``uq_session_emotion``.
    """

    __tablename__ = "emotion_assessments"

    __table_args__ = (
        UniqueConstraint("session_id", "emotion", name="uq_session_emotion"),
        CheckConstraint(
            "intensity BETWEEN 0 AND 10", name="ck_emotion_intensity",
        ),
        CheckConstraint(
            "source IN ('structured', 'free_text_extracted')",
            name="ck_emotion_source",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4,
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assessment_sessions.id", ondelete="CASCADE"),
    )
    # Named emotion, e.g. "anxiety", "joy", "stress".
    emotion: Mapped[str] = mapped_column(Text)
    # How often the emotion occurs, e.g. "rarely", "often".
    frequency: Mapped[str] = mapped_column(Text)
    # Subjective intensity on a 0–10 scale (self-reported).
    intensity: Mapped[int] = mapped_column(SmallInteger)
    # Typical duration, e.g. "minutes", "days".
    duration: Mapped[str] = mapped_column(Text)
    # Perceived impact on daily functioning; default "none".
    impact: Mapped[str] = mapped_column(Text, default="none")
    # How the user typically responds to the emotion (optional).
    response: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Coping mechanism used (optional).
    coping_strategy: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Composite burden index (frequency × intensity × duration weighting).
    burden_index: Mapped[Decimal] = mapped_column(Numeric(5, 1))
    # Coarse intensity band derived from burden_index.
    band: Mapped[EmotionBand] = mapped_column(
        SAEnum(EmotionBand, name="emotion_band", create_constraint=True, validate_strings=True),
    )
    # "structured" (form input) or "free_text_extracted" (NLP).
    source: Mapped[str] = mapped_column(Text, default="structured")


# ---------------------------------------------------------------------------
# Emotional trigger codes
# ---------------------------------------------------------------------------


class EmotionalTrigger(Base):
    """A single trigger code associated with an emotion assessment.

    Stored as separate rows (not an array) for efficient filtering in
    recommendation matching rules.  E.g. "work_pressure", "conflict".
    """

    __tablename__ = "emotional_triggers"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4,
    )
    emotion_assessment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("emotion_assessments.id", ondelete="CASCADE"),
    )
    # Short code identifying the trigger, e.g. "work_pressure".
    trigger_code: Mapped[str] = mapped_column(Text)


# ---------------------------------------------------------------------------
# Assessment report snapshots
# ---------------------------------------------------------------------------


class AssessmentReport(Base):
    """Immutable snapshot of a completed session's results.

    One report per session (``uq_report_session``).  The JSON is split
    into two fields:

    ``structured``  — deterministic numbers, labels, and metadata
                      (the source of truth; always present).
    ``narrative``   — LLM-generated prose fields; NULL until generated.

    Separating the two allows the narrative to be regenerated without
    altering the authoritative numeric record.  ``prompt_version``
    tracks the LLM prompt template used so narrative regenerations are
    reproducible.  ``pdf_object_key`` stores the S3/object-storage key
    for a generated PDF report (NULL until produced).
    """

    __tablename__ = "assessment_reports"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4,
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assessment_sessions.id", ondelete="CASCADE"),
        unique=True,  # Enforces uq_report_session.
        index=True,
    )
    # Deterministic score + label payload (source of truth).
    structured: Mapped[dict] = mapped_column(JSON)
    # LLM-generated prose; NULL until narrative generation runs.
    narrative: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Identifier of the LLM model that produced the narrative.
    llm_model: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Version of the prompt template used for narrative generation.
    prompt_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Object-storage key for the generated PDF (NULL until produced).
    pdf_object_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
