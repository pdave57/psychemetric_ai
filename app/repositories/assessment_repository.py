"""Assessment repository: seed data, instrument lookup, session management,
and response persistence.

All functions perform queries, adds, and flushes — they do NOT commit.
Transaction ownership (commit / rollback) belongs to the service layer.
"""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    AssessmentVersion,
    AssessmentSession,
    Question,
    QuestionOption,
    UserResponse,
    SessionStatus,
    ItemKind,
)

# ---------------------------------------------------------------------------
# Seed data: prototype 16-item temperament questionnaire
# ---------------------------------------------------------------------------

# (code, text, area, dimension_load, reverse_coded)
# Stored as forced_choice items; the 'loads' field carries per-dimension weight.
_ITEMS = [
    ("SAN01", "I feel energised when interacting with a group of people.",       "social_behaviour",  "sanguine",   False),
    ("SAN02", "I readily express excitement when something interests me.",        "social_behaviour",  "sanguine",   False),
    ("SAN03", "I enjoy spontaneous social activities.",                           "social_behaviour",  "sanguine",   False),
    ("SAN04", "I usually prefer to keep to myself at social gatherings.",         "social_behaviour",  "sanguine",   True),
    ("CHO01", "I am comfortable taking the lead when a decision is needed.",      "decision_making",   "choleric",   False),
    ("CHO02", "I make decisions promptly when I have enough information.",        "decision_making",   "choleric",   False),
    ("CHO03", "I set challenging goals and work persistently toward them.",       "goal_setting",      "choleric",   False),
    ("CHO04", "I avoid taking responsibility when a group needs direction.",      "decision_making",   "choleric",   True),
    ("MEL01", "I think carefully about details before completing a task.",        "analytical",        "melancholic",False),
    ("MEL02", "I reflect on my experiences to understand what went well or badly.","analytical",       "melancholic",False),
    ("MEL03", "I notice small errors or inconsistencies in my work.",             "analytical",        "melancholic",False),
    ("MEL04", "I rarely think through the possible consequences of my decisions.","analytical",        "melancholic",True),
    ("PHL01", "I remain patient when other people disagree with me.",             "interpersonal",     "phlegmatic", False),
    ("PHL02", "I prefer to resolve disagreements calmly.",                        "interpersonal",     "phlegmatic", False),
    ("PHL03", "People can generally rely on me to be steady and consistent.",     "interpersonal",     "phlegmatic", False),
    ("PHL04", "I become impatient quickly when plans change.",                    "interpersonal",     "phlegmatic", True),
]

# Likert-scale options shared across all items.
_OPTIONS = [
    ("strongly_disagree", "Strongly disagree"),
    ("disagree",          "Disagree"),
    ("neutral",           "Neither agree nor disagree"),
    ("agree",             "Agree"),
    ("strongly_agree",    "Strongly agree"),
]

_INSTRUMENT_CODE    = "innermap_temperament"
_INSTRUMENT_VERSION = "0.1.0"


def seed_initial_instrument(db: Session) -> AssessmentVersion:
    """Idempotently seed the prototype instrument and its questions.

    Returns the existing row if already present, so repeated calls on
    the same database are safe.
    """
    existing = db.scalar(
        select(AssessmentVersion).where(
            AssessmentVersion.instrument == _INSTRUMENT_CODE,
            AssessmentVersion.version   == _INSTRUMENT_VERSION,
        )
    )
    if existing:
        return existing

    instrument = AssessmentVersion(
        instrument     = _INSTRUMENT_CODE,
        version        = _INSTRUMENT_VERSION,
        status         = "draft",
        config         = {"scale_min": 1, "scale_max": 5},
        content_sha256 = "prototype-no-hash",
    )
    db.add(instrument)
    db.flush()  # Obtain instrument.id before inserting questions.

    for n, (code, text, area, dimension, reverse) in enumerate(_ITEMS, start=1):
        q = Question(
            version_id   = instrument.id,
            code         = code,
            text         = text,
            area         = area,
            kind         = ItemKind.likert,
            weight       = Decimal("1.0"),
            is_core      = True,
            reverse_coded= reverse,
            loads        = {dimension: 1.0},
            sort_order   = n,
        )
        db.add(q)
        db.flush()  # Obtain q.id before inserting options.

        db.add_all([
            QuestionOption(
                question_id = q.id,
                code        = opt_code,
                text        = opt_text,
                evidence    = {},
            )
            for opt_code, opt_text in _OPTIONS
        ])

    db.commit()
    return instrument


# ---------------------------------------------------------------------------
# Instrument lookup
# ---------------------------------------------------------------------------


def get_instrument(db: Session, code: str, version: str) -> AssessmentVersion | None:
    """Return an instrument version by its (code, version) pair, or None."""
    return db.scalar(
        select(AssessmentVersion).where(
            AssessmentVersion.instrument == code,
            AssessmentVersion.version    == version,
        )
    )


# ---------------------------------------------------------------------------
# Session management
# ---------------------------------------------------------------------------


def create_session(db: Session, user_id, instrument: AssessmentVersion) -> AssessmentSession:
    """Create and persist an in-progress session for *user_id* on *instrument*.

    ``user_id`` may be a UUID object or a string; the column type is Uuid
    so SQLAlchemy handles coercion.  The service layer owns the commit.
    """
    s = AssessmentSession(user_id=user_id, version_id=instrument.id)
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


# ---------------------------------------------------------------------------
# Question and option retrieval
# ---------------------------------------------------------------------------


def get_questions(db: Session, version_id) -> list[Question]:
    """Return all questions for *version_id* ordered by sort_order."""
    return db.scalars(
        select(Question)
        .where(Question.version_id == version_id)
        .order_by(Question.sort_order)
    ).all()


def get_options(db: Session, question_id) -> list[QuestionOption]:
    """Return all options for *question_id* ordered by code."""
    return db.scalars(
        select(QuestionOption)
        .where(QuestionOption.question_id == question_id)
        .order_by(QuestionOption.code)
    ).all()


# ---------------------------------------------------------------------------
# Response persistence
# ---------------------------------------------------------------------------


def get_responses(db: Session, session_id) -> list[UserResponse]:
    """Return all responses submitted in *session_id*."""
    return db.scalars(
        select(UserResponse).where(UserResponse.session_id == session_id)
    ).all()


def save_response(db: Session, session_id, question_id, likert_value: int, seq: int) -> UserResponse:
    """Upsert a Likert response for *(session_id, question_id)*.

    If a response already exists it is updated in place.  The caller
    must flush or commit after calling this function.
    """
    r = db.scalar(
        select(UserResponse).where(
            UserResponse.session_id  == session_id,
            UserResponse.question_id == question_id,
        )
    )
    if r:
        r.likert_value = likert_value
    else:
        r = UserResponse(
            session_id   = session_id,
            question_id  = question_id,
            likert_value = likert_value,
            seq          = seq,
        )
        db.add(r)
    db.flush()
    return r
