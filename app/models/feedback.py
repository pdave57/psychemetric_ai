"""User feedback model for measuring platform experience and modern 5-question surveys."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    SmallInteger,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class UserFeedback(Base):
    """Stores a user's experience rating (1-10) and 5-question modern feedback response."""

    __tablename__ = "user_feedback"

    __table_args__ = (
        CheckConstraint("experience_rating BETWEEN 1 AND 10", name="ck_feedback_experience_range"),
        CheckConstraint("ease_of_use BETWEEN 1 AND 5", name="ck_feedback_ease_range"),
        CheckConstraint("insightfulness BETWEEN 1 AND 5", name="ck_feedback_insight_range"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    session_id: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # Q1: Overall experience (1-10)
    experience_rating: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    # Q2: Clarity and ease of use (1-5)
    ease_of_use: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    # Q3: Insightfulness and relevance of results (1-5)
    insightfulness: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    # Q4: Most valuable aspect (structured choice) + recommendation signal
    most_valuable_aspect: Mapped[str] = mapped_column(String(64), nullable=False)
    would_recommend: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Q5: Open-ended improvement / qualitative feedback
    improvement_comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
