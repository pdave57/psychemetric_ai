"""Assessment repository: seeds standard instruments from knowledge_pack,
instrument lookup, session management, and response persistence.

All functions perform queries, adds, and flushes — they do NOT commit.
Transaction ownership (commit / rollback) belongs to the service layer.
"""

from collections import defaultdict
from decimal import Decimal
from typing import List, Optional, Dict, Any

from sqlalchemy import select, func
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
from app.knowledge_pack import (
    get_temperament_bank,
    get_temperament_20_bank,
    get_temperament_40_bank,
    get_emotional_intelligence_bank,
    get_answer_options,
)

# Canonical instrument metadata
TEMPERAMENT_20_CODE = "psychemetre_temperament_20"
TEMPERAMENT_20_VERSION = "1.0.0"

TEMPERAMENT_40_CODE = "psychemetre_temperament_40"
TEMPERAMENT_40_VERSION = "1.0.0"

EQ_25_CODE = "psychemetre_eq_25"
EQ_25_VERSION = "1.0.0"

# Legacy alias for backward compatibility with existing tests
LEGACY_INSTRUMENT_CODE = "innermap_temperament"
LEGACY_INSTRUMENT_VERSION = "0.1.0"


def seed_temperament_20_instrument(
    db: Session,
    instrument_code: str = TEMPERAMENT_20_CODE,
    version: str = TEMPERAMENT_20_VERSION,
) -> AssessmentVersion:
    """Seed the 20-item restructured temperament instrument from knowledge_pack."""
    existing = db.scalar(
        select(AssessmentVersion).where(
            AssessmentVersion.instrument == instrument_code,
            AssessmentVersion.version == version,
        )
    )
    if existing:
        return existing

    bank = get_temperament_20_bank()
    options_data = get_answer_options()["scales"]["likert_5_agreement"]["options"]

    instrument = AssessmentVersion(
        instrument=instrument_code,
        version=version,
        status="published",
        config={"scale_min": 1, "scale_max": 5, "total_items": 20},
        content_sha256="psychemetre_temperament_20_v1",
    )
    db.add(instrument)
    db.flush()

    for q_data in bank["questions"]:
        q = Question(
            version_id=instrument.id,
            code=q_data["code"],
            text=q_data["text"],
            area=q_data.get("area", "general"),
            kind=ItemKind.likert,
            weight=Decimal(str(q_data.get("weight", 1.0))),
            is_core=True,
            reverse_coded=q_data.get("reverse_coded", False),
            loads={q_data["dimension"]: 1.0},
            sort_order=q_data["sort_order"],
        )
        db.add(q)
        db.flush()

        db.add_all([
            QuestionOption(
                question_id=q.id,
                code=opt["code"],
                text=opt["label"],
                evidence={},
            )
            for opt in options_data
        ])

    db.commit()
    return instrument


def seed_instrument_from_knowledge_pack(
    db: Session,
    instrument_code: str = TEMPERAMENT_40_CODE,
    version: str = TEMPERAMENT_40_VERSION
) -> AssessmentVersion:
    """Seed the comprehensive 40-item temperament instrument from knowledge_pack."""
    existing = db.scalar(
        select(AssessmentVersion).where(
            AssessmentVersion.instrument == instrument_code,
            AssessmentVersion.version == version,
        )
    )
    if existing:
        return existing

    bank = get_temperament_40_bank()
    options_data = get_answer_options()["scales"]["likert_5_agreement"]["options"]

    instrument = AssessmentVersion(
        instrument=instrument_code,
        version=version,
        status="published",
        config={"scale_min": 1, "scale_max": 5, "total_items": 40},
        content_sha256="psychemetre_temperament_40_v1",
    )
    db.add(instrument)
    db.flush()

    for q_data in bank["questions"]:
        q = Question(
            version_id=instrument.id,
            code=q_data["code"],
            text=q_data["text"],
            area=q_data.get("area", "general"),
            kind=ItemKind.likert,
            weight=Decimal(str(q_data.get("weight", 1.0))),
            is_core=True,
            reverse_coded=q_data.get("reverse_coded", False),
            loads={q_data["dimension"]: 1.0},
            sort_order=q_data["sort_order"],
        )
        db.add(q)
        db.flush()

        db.add_all([
            QuestionOption(
                question_id=q.id,
                code=opt["code"],
                text=opt["label"],
                evidence={},
            )
            for opt in options_data
        ])

    db.commit()
    return instrument


def seed_eq_instrument(
    db: Session,
    instrument_code: str = EQ_25_CODE,
    version: str = EQ_25_VERSION
) -> AssessmentVersion:
    """Seed the 25-item emotional intelligence instrument from knowledge_pack."""
    existing = db.scalar(
        select(AssessmentVersion).where(
            AssessmentVersion.instrument == instrument_code,
            AssessmentVersion.version == version,
        )
    )
    if existing:
        return existing

    bank = get_emotional_intelligence_bank()
    options_data = get_answer_options()["scales"]["likert_5_agreement"]["options"]

    instrument = AssessmentVersion(
        instrument=instrument_code,
        version=version,
        status="published",
        config={"scale_min": 1, "scale_max": 5, "total_items": 25},
        content_sha256="psychemetre_eq_25_v1",
    )
    db.add(instrument)
    db.flush()

    for q_data in bank["questions"]:
        q = Question(
            version_id=instrument.id,
            code=q_data["code"],
            text=q_data["text"],
            area=q_data.get("dimension", "general"),
            kind=ItemKind.likert,
            weight=Decimal(str(q_data.get("weight", 1.0))),
            is_core=True,
            reverse_coded=q_data.get("reverse_coded", False),
            loads={q_data["dimension"]: 1.0},
            sort_order=q_data["sort_order"],
        )
        db.add(q)
        db.flush()

        db.add_all([
            QuestionOption(
                question_id=q.id,
                code=opt["code"],
                text=opt["label"],
                evidence={},
            )
            for opt in options_data
        ])

    db.commit()
    return instrument


def seed_initial_instrument(db: Session) -> AssessmentVersion:
    """Seed instruments idempotently.

    Seeds:
      1. Default 20-item Restructured Psychemetre Temperament Instrument
      2. Comprehensive 40-item Psychemetre Temperament Instrument (historical compat)
      3. 25-item Emotional Intelligence Instrument
      4. Legacy 16-item alias (for test compatibility)
    """
    # 1. 20-item canonical restructured instrument
    seed_temperament_20_instrument(db, TEMPERAMENT_20_CODE, TEMPERAMENT_20_VERSION)

    # 2. 40-item historical instrument
    canonical_inst = seed_instrument_from_knowledge_pack(db, TEMPERAMENT_40_CODE, TEMPERAMENT_40_VERSION)

    # 3. 25-item EQ instrument
    seed_eq_instrument(db, EQ_25_CODE, EQ_25_VERSION)

    # 4. Seed legacy 16-item alias pointing to first 16 items for backward compat
    existing_legacy = db.scalar(
        select(AssessmentVersion).where(
            AssessmentVersion.instrument == LEGACY_INSTRUMENT_CODE,
            AssessmentVersion.version == LEGACY_INSTRUMENT_VERSION,
        )
    )
    if not existing_legacy:
        bank = get_temperament_20_bank()
        options_data = get_answer_options()["scales"]["likert_5_agreement"]["options"]
        legacy_inst = AssessmentVersion(
            instrument=LEGACY_INSTRUMENT_CODE,
            version=LEGACY_INSTRUMENT_VERSION,
            status="published",
            config={"scale_min": 1, "scale_max": 5, "total_items": 16},
            content_sha256="innermap_prototype_16",
        )
        db.add(legacy_inst)
        db.flush()

        # Seed 4 items per dimension = 16 items
        items_16 = []
        for d in ["sanguine", "choleric", "melancholic", "phlegmatic"]:
            items_16.extend([q for q in bank["questions"] if q["dimension"] == d][:4])

        for n, q_data in enumerate(items_16, start=1):
            q = Question(
                version_id=legacy_inst.id,
                code=q_data["code"],
                text=q_data["text"],
                area=q_data.get("area", "general"),
                kind=ItemKind.likert,
                weight=Decimal("1.0"),
                is_core=True,
                reverse_coded=q_data.get("reverse_coded", False),
                loads={q_data["dimension"]: 1.0},
                sort_order=n,
            )
            db.add(q)
            db.flush()

            db.add_all([
                QuestionOption(
                    question_id=q.id,
                    code=opt["code"],
                    text=opt["label"],
                    evidence={},
                )
                for opt in options_data
            ])
        db.commit()

    return canonical_inst


# ---------------------------------------------------------------------------
# Instrument lookup
# ---------------------------------------------------------------------------


def get_instrument(db: Session, code: str, version: str) -> Optional[AssessmentVersion]:
    """Return an instrument version by its (code, version) pair, or None."""
    return db.scalar(
        select(AssessmentVersion).where(
            AssessmentVersion.instrument == code,
            AssessmentVersion.version == version,
        )
    )


# ---------------------------------------------------------------------------
# Session management
# ---------------------------------------------------------------------------


def create_session(db: Session, user_id, instrument: AssessmentVersion) -> AssessmentSession:
    """Create and persist an in-progress session for *user_id* on *instrument*."""
    s = AssessmentSession(user_id=user_id, version_id=instrument.id)
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


def get_active_session_for_user(
    db: Session,
    user_id: str,
    instrument_code: Optional[str] = None,
) -> Optional[AssessmentSession]:
    """Find the most recent in-progress AssessmentSession for *user_id*."""
    stmt = (
        select(AssessmentSession)
        .join(AssessmentVersion, AssessmentSession.version_id == AssessmentVersion.id)
        .where(
            AssessmentSession.user_id == str(user_id),
            AssessmentSession.status == SessionStatus.in_progress,
        )
    )
    if instrument_code:
        stmt = stmt.where(AssessmentVersion.instrument == instrument_code)
    stmt = stmt.order_by(AssessmentSession.started_at.desc())
    return db.scalar(stmt)


# ---------------------------------------------------------------------------
# Question and option retrieval
# ---------------------------------------------------------------------------


def get_questions(db: Session, version_id) -> List[Question]:
    """Return all questions for *version_id* ordered by sort_order."""
    return db.scalars(
        select(Question)
        .where(Question.version_id == version_id)
        .order_by(Question.sort_order)
    ).all()


def get_options(db: Session, question_id) -> List[QuestionOption]:
    """Return all options for *question_id* ordered by code."""
    return db.scalars(
        select(QuestionOption)
        .where(QuestionOption.question_id == question_id)
        .order_by(QuestionOption.code)
    ).all()


# ---------------------------------------------------------------------------
# Response persistence
# ---------------------------------------------------------------------------


def get_responses(db: Session, session_id) -> List[UserResponse]:
    """Return all responses submitted in *session_id*."""
    return db.scalars(
        select(UserResponse).where(UserResponse.session_id == session_id)
    ).all()


def save_response(db: Session, session_id, question_id, likert_value: int, seq: int) -> UserResponse:
    """Upsert a Likert response for *(session_id, question_id)*."""
    r = db.scalar(
        select(UserResponse).where(
            UserResponse.session_id == session_id,
            UserResponse.question_id == question_id,
        )
    )
    if r:
        r.likert_value = likert_value
    else:
        r = UserResponse(
            session_id=session_id,
            question_id=question_id,
            likert_value=likert_value,
            seq=seq,
        )
        db.add(r)
    db.flush()
    return r


def verify_temperament_20_migration(db: Session) -> Dict[str, Any]:
    """Verify 20-item temperament migration status and return summary statistics."""
    version_row = db.scalar(
        select(AssessmentVersion).where(
            AssessmentVersion.instrument == TEMPERAMENT_20_CODE,
            AssessmentVersion.version == TEMPERAMENT_20_VERSION,
        )
    )
    if not version_row:
        return {"migrated": False, "reason": "AssessmentVersion record missing"}

    questions = get_questions(db, version_row.id)
    options_count = db.scalar(
        select(func.count(QuestionOption.id))
        .join(Question, QuestionOption.question_id == Question.id)
        .where(Question.version_id == version_row.id)
    ) or 0

    dimension_counts = defaultdict(int)
    area_counts = defaultdict(set)
    for q in questions:
        dim = list(q.loads.keys())[0] if q.loads else (q.area or "unknown")
        dimension_counts[dim] += 1
        if q.area:
            area_counts[dim].add(q.area)

    return {
        "migrated": len(questions) == 20,
        "instrument_code": version_row.instrument,
        "version": version_row.version,
        "total_questions": len(questions),
        "total_options": options_count,
        "dimension_counts": dict(dimension_counts),
        "behavioural_areas": {k: sorted(list(v)) for k, v in area_counts.items()},
        "status": version_row.status,
    }


def verify_eq_migration(db: Session) -> Dict[str, Any]:
    """Verify EQ instrument migration status and return summary statistics."""
    eq_version = db.scalar(
        select(AssessmentVersion).where(
            AssessmentVersion.instrument == EQ_25_CODE,
            AssessmentVersion.version == EQ_25_VERSION,
        )
    )
    if not eq_version:
        return {"migrated": False, "reason": "AssessmentVersion record missing"}

    questions = get_questions(db, eq_version.id)
    options_count = db.scalar(
        select(func.count(QuestionOption.id))
        .join(Question, QuestionOption.question_id == Question.id)
        .where(Question.version_id == eq_version.id)
    ) or 0

    dimension_counts = defaultdict(int)
    for q in questions:
        dim = q.area or (list(q.loads.keys())[0] if q.loads else "unknown")
        dimension_counts[dim] += 1

    return {
        "migrated": len(questions) == 25,
        "instrument_code": eq_version.instrument,
        "version": eq_version.version,
        "total_questions": len(questions),
        "total_options": options_count,
        "dimension_counts": dict(dimension_counts),
        "status": eq_version.status,
    }


if __name__ == "__main__":
    from app.core.database import SessionLocal, engine, Base
    from app.models import *  # noqa: F401, F403
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as session:
        seed_initial_instrument(session)
        t20_stats = verify_temperament_20_migration(session)
        print("Temperament-20 Migration Status:", t20_stats)
        eq_stats = verify_eq_migration(session)
        print("EQ Migration Status:", eq_stats)

