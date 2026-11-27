"""Assessment catalogue routes: list available instruments and standard items."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db, run_sync
from app.models.instrument import AssessmentVersion
from app.knowledge_pack import (
    get_temperament_bank,
    get_temperament_20_bank,
    get_temperament_40_bank,
    get_emotional_intelligence_bank,
    get_emotional_intelligence_15_bank,
    get_emotional_intelligence_25_bank,
    get_emotion_indicators_bank,
    get_answer_options,
)

router = APIRouter()


@router.get("/instruments")
async def list_available_instruments(db: Session = Depends(get_db)):
    """List all seeded assessment instruments."""
    versions = await run_sync(lambda: db.scalars(select(AssessmentVersion)).all())
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
async def get_scales():
    """Retrieve standard assessment scales and response option structures."""
    return await run_sync(get_answer_options)


@router.get("/knowledge-pack/temperament")
async def get_temperament_catalog():
    """Retrieve the standard 20-item classical temperament item bank."""
    return await run_sync(get_temperament_bank)


@router.get("/knowledge-pack/temperament-20")
async def get_temperament_20_catalog():
    """Retrieve the 20-item classical temperament item bank."""
    return await run_sync(get_temperament_20_bank)


@router.get("/knowledge-pack/temperament-40")
async def get_temperament_40_catalog():
    """Retrieve the 40-item classical temperament item bank (historical)."""
    return await run_sync(get_temperament_40_bank)


@router.get("/knowledge-pack/emotional-intelligence")
async def get_eq_catalog():
    """Retrieve the standard 15-item emotional intelligence competency bank."""
    return await run_sync(get_emotional_intelligence_bank)


@router.get("/knowledge-pack/emotional-intelligence-15")
async def get_eq_15_catalog():
    """Retrieve the 15-item emotional self-assessment bank (emotional skills)."""
    return await run_sync(get_emotional_intelligence_15_bank)


@router.get("/knowledge-pack/emotional-intelligence-25")
async def get_eq_25_catalog():
    """Retrieve the 25-item emotional intelligence competency bank (historical)."""
    return await run_sync(get_emotional_intelligence_25_bank)


@router.get("/knowledge-pack/emotions")
async def get_emotions_catalog():
    """Retrieve the 9 discrete emotion indicator profiles with triggers and coping strategies."""
    return await run_sync(get_emotion_indicators_bank)
