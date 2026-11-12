"""Versioned psychometric instrument catalogue.

Tables
------
assessment_versions    Immutable instrument snapshots (questions + config).
assessment_domains     Named scoring dimensions within an instrument.
questions              Individual items (forced-choice or Likert).
question_options       Selectable answers for each question.
consistency_pairs      Linked question pairs for internal-consistency checks.
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import InstrumentStatus, ItemKind


# ---------------------------------------------------------------------------
# Instrument versions (immutable once published)
# ---------------------------------------------------------------------------


class AssessmentVersion(Base):
    """A versioned snapshot of a psychometric instrument.

    The (instrument, version) pair is unique.  Once ``status`` moves to
    ``published`` the row is treated as immutable: every assessment
    session pins the exact version it was administered with.
    """

    __tablename__ = "assessment_versions"

    __table_args__ = (
        UniqueConstraint("instrument", "version", name="uq_instrument_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4,
    )
    # Short identifier, e.g. "innermap_temperament".
    instrument: Mapped[str] = mapped_column(Text)
    # Semantic version string, e.g. "0.1.0".
    version: Mapped[str] = mapped_column(Text)
    status: Mapped[InstrumentStatus] = mapped_column(
        SAEnum(
            InstrumentStatus,
            name="instrument_status",
            create_constraint=True,
            validate_strings=True,
        ),
        default=InstrumentStatus.draft,
    )
    # EngineConfig snapshot (scoring thresholds, scale parameters).
    config: Mapped[dict] = mapped_column(JSON)
    # SHA-256 of the exported instrument JSON for integrity verification.
    content_sha256: Mapped[str] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )


# ---------------------------------------------------------------------------
# Scoring domains within an instrument
# ---------------------------------------------------------------------------


class AssessmentDomain(Base):
    """A named scoring dimension (e.g. *sanguine*, *anxiety*) belonging to
    an instrument version.

    ``kind`` classifies the domain as temperament, emotion, or
    personality for downstream routing and display.
    """

    __tablename__ = "assessment_domains"

    __table_args__ = (
        UniqueConstraint("version_id", "code", name="uq_version_domain"),
        CheckConstraint(
            "kind IN ('temperament', 'emotion', 'personality')",
            name="ck_domain_kind",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4,
    )
    version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assessment_versions.id"),
    )
    # Domain code, e.g. "sanguine", "choleric", "anger", "anxiety".
    code: Mapped[str] = mapped_column(Text)
    # Broad category: temperament | emotion | personality.
    kind: Mapped[str] = mapped_column(Text)
    # Human-readable label for display.
    label: Mapped[str] = mapped_column(Text)


# ---------------------------------------------------------------------------
# Question bank
# ---------------------------------------------------------------------------


class Question(Base):
    """A single item in a psychometric instrument.

    ``kind`` determines the response format: ``forced_choice`` items
    present a set of options with evidence weights, while ``likert``
    items use a numeric scale.

    ``reverse_coded`` instructs the scoring engine to invert the raw
    response value before aggregation.  ``loads`` stores per-dimension
    factor loadings for Likert items (e.g. ``{"sanguine": 0.8}``).
    """

    __tablename__ = "questions"

    __table_args__ = (
        UniqueConstraint("version_id", "code", name="uq_version_question"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4,
    )
    version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assessment_versions.id"),
    )
    # Item code, e.g. "fc_social_1", "SAN01".
    code: Mapped[str] = mapped_column(Text)
    # Behavioural area, e.g. "social_behaviour", "decision_making".
    area: Mapped[str] = mapped_column(Text)
    kind: Mapped[ItemKind] = mapped_column(
        SAEnum(ItemKind, name="item_kind", create_constraint=True, validate_strings=True),
    )
    # The question text shown to the user.
    text: Mapped[str] = mapped_column(Text)
    # Scoring weight (default 1.0; provisional, pending expert review).
    weight: Mapped[Decimal] = mapped_column(Numeric(5, 3), default=Decimal("1.0"))
    # Whether this item is mandatory for a valid score.
    is_core: Mapped[bool] = mapped_column(Boolean, default=False)
    # Whether scoring should invert the response value.
    reverse_coded: Mapped[bool] = mapped_column(Boolean, default=False)
    # Per-dimension factor loadings for Likert items.
    loads: Mapped[dict] = mapped_column(JSON, default=dict)
    # Presentation order within the instrument.
    sort_order: Mapped[int] = mapped_column(Integer)


# ---------------------------------------------------------------------------
# Fixed answer options per question
# ---------------------------------------------------------------------------


class QuestionOption(Base):
    """A selectable response for a question.

    For forced-choice items, ``evidence`` carries per-dimension weights
    (e.g. ``{"sanguine": 0.8, "choleric": 0.1}``).  ``is_unsure``
    flags the "I'm not sure" escape-hatch option.
    """

    __tablename__ = "question_options"

    __table_args__ = (
        UniqueConstraint("question_id", "code", name="uq_question_option"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4,
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"),
    )
    # Short code, e.g. "strongly_agree", "option_a".
    code: Mapped[str] = mapped_column(Text)
    # Display text, e.g. "Strongly agree".
    text: Mapped[str] = mapped_column(Text)
    # Per-dimension evidence weights for forced-choice scoring.
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)
    # Whether this option is the "I'm not sure" escape hatch.
    is_unsure: Mapped[bool] = mapped_column(Boolean, default=False)


# ---------------------------------------------------------------------------
# Internal consistency verification
# ---------------------------------------------------------------------------


class ConsistencyPair(Base):
    """A linked pair of questions used for internal-consistency checks.

    ``relation`` is either ``same`` (both items should score in the same
    direction for a consistent respondent) or ``opposite`` (one should
    score high when the other scores low).
    """

    __tablename__ = "consistency_pairs"

    __table_args__ = (
        CheckConstraint(
            "relation IN ('same', 'opposite')",
            name="ck_consistency_relation",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4,
    )
    version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assessment_versions.id"),
    )
    question_a: Mapped[uuid.UUID] = mapped_column(ForeignKey("questions.id"))
    question_b: Mapped[uuid.UUID] = mapped_column(ForeignKey("questions.id"))
    # Temperament dimension being checked.
    dimension: Mapped[str] = mapped_column(Text)
    # "same" or "opposite".
    relation: Mapped[str] = mapped_column(Text)
