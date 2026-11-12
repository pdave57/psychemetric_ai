"""Application-wide enum types mirroring PostgreSQL ENUM definitions.

Each enum is a ``str`` subclass so that SQLAlchemy transparently
serialises values to native PostgreSQL ENUMs in production and to
CHECK-constrained TEXT columns in SQLite test databases.
"""

import enum


class UserRole(str, enum.Enum):
    """Privilege level assigned to a platform account."""

    user = "user"
    researcher = "researcher"
    admin = "admin"


class InstrumentStatus(str, enum.Enum):
    """Lifecycle stage of an assessment instrument version."""

    draft = "draft"
    pilot = "pilot"
    published = "published"
    retired = "retired"


class ItemKind(str, enum.Enum):
    """Response format of a question item."""

    forced_choice = "forced_choice"
    likert = "likert"


class SessionStatus(str, enum.Enum):
    """State machine for an assessment session.

    Transitions: in_progress → completed | safety_paused | abandoned.
    """

    in_progress = "in_progress"
    safety_paused = "safety_paused"
    completed = "completed"
    abandoned = "abandoned"


class ConsentType(str, enum.Enum):
    """Category of user consent record."""

    terms_privacy = "terms_privacy"
    assessment_processing = "assessment_processing"
    research_use = "research_use"
    model_training = "model_training"


class SafetyLevel(str, enum.Enum):
    """Severity classification for safety-flagged content."""

    high = "high"
    critical = "critical"


class EvidenceLevel(str, enum.Enum):
    """Strength-of-evidence tag for recommendations and knowledge."""

    unreviewed_seed = "unreviewed_seed"
    expert_reviewed = "expert_reviewed"
    research_supported = "research_supported"
    clinical_guideline = "clinical_guideline"


class RecStatus(str, enum.Enum):
    """Lifecycle state of a personalised recommendation."""

    suggested = "suggested"
    accepted = "accepted"
    in_progress = "in_progress"
    completed = "completed"
    dismissed = "dismissed"


class EmotionBand(str, enum.Enum):
    """Coarse intensity band derived from burden_index."""

    low = "low"
    moderate = "moderate"
    high = "high"
