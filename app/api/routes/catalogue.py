"""Assessment catalogue routes: list available instruments and standard items."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.instrument import AssessmentVersion
from app.knowledge_pack import (
    get_temperament_bank,
    get_temperament_20_bank,
    get_temperament_40_bank,
    get_emotional_intelligence_bank,
    get_emotion_indicators_bank,
    get_answer_options,
)

router = APIRouter()


@router.get("/instruments")
def list_available_instruments(db: Session = Depends(get_db)):
    """List all seeded assessment instruments."""
    versions = db.scalars(select(AssessmentVersion)).all()
    return {
        "instruments": [
            {
                "id": str(v.id),
                "code": v.instrument,
                "version": v.version,
                "status": v.status.value,
                "config": v.config,
            }
            for v in versions
        ]
    }


@router.get("/knowledge-pack/scales")
def get_scales():
    """Retrieve standard assessment scales and response option structures."""
    return get_answer_options()


@router.get("/knowledge-pack/temperament")
def get_temperament_catalog():
    """Retrieve the standard 20-item classical temperament item bank."""
    return get_temperament_bank()


@router.get("/knowledge-pack/temperament-20")
def get_temperament_20_catalog():
    """Retrieve the 20-item classical temperament item bank."""
    return get_temperament_20_bank()


@router.get("/knowledge-pack/temperament-40")
def get_temperament_40_catalog():
    """Retrieve the 40-item classical temperament item bank (historical)."""
    return get_temperament_40_bank()


@router.get("/knowledge-pack/emotional-intelligence")
def get_eq_catalog():
    """Retrieve the standard 25-item emotional intelligence competency bank."""
    return get_emotional_intelligence_bank()


@router.get("/knowledge-pack/emotions")
def get_emotions_catalog():
    """Retrieve the 9 discrete emotion indicator profiles with triggers and coping strategies."""
    return get_emotion_indicators_bank()
