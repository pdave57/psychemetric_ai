"""Re-export every ORM model so the rest of the app can do::

    from app.models import AssessmentSession, Question, ...

and so Alembic's ``target_metadata = Base.metadata`` picks up all 18 tables.
"""

# Enums (must import first so SA enum types are registered before models)
from app.models.enums import (
    UserRole,
    InstrumentStatus,
    ItemKind,
    SessionStatus,
    ConsentType,
    SafetyLevel,
    EvidenceLevel,
    RecStatus,
    EmotionBand,
)

# Identity & consent
from app.models.user import User, ConsentRecord

# Instrument catalogue
from app.models.instrument import (
    AssessmentVersion,
    AssessmentDomain,
    Question,
    QuestionOption,
    ConsistencyPair,
)

# Sessions & responses
from app.models.session import AssessmentSession, UserResponse

# Results
from app.models.result import (
    TemperamentScore,
    EmotionAssessment,
    EmotionalTrigger,
    AssessmentReport,
)

# Recommendations
from app.models.recommendation import (
    RecommendationTemplate,
    Recommendation,
    RecommendationHistory,
)

# Safety & audit
from app.models.safety import SafetyEvent, AuditLog

# Knowledge base
from app.models.knowledge import KnowledgeDocument, KnowledgeChunk

# User feedback
from app.models.feedback import UserFeedback

__all__ = [
    # enums
    "UserRole", "InstrumentStatus", "ItemKind", "SessionStatus",
    "ConsentType", "SafetyLevel", "EvidenceLevel", "RecStatus", "EmotionBand",
    # identity
    "User", "ConsentRecord",
    # instrument
    "AssessmentVersion", "AssessmentDomain", "Question", "QuestionOption", "ConsistencyPair",
    # session
    "AssessmentSession", "UserResponse",
    # results
    "TemperamentScore", "EmotionAssessment", "EmotionalTrigger", "AssessmentReport",
    # recommendations
    "RecommendationTemplate", "Recommendation", "RecommendationHistory",
    # safety
    "SafetyEvent", "AuditLog",
    # knowledge
    "KnowledgeDocument", "KnowledgeChunk",
    # feedback
    "UserFeedback",
]
