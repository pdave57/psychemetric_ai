"""History routes: query past assessment sessions, scores, and comparisons."""

import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.dependencies import get_current_user
from app.models.user import User
from app.models.session import AssessmentSession
from app.models.result import TemperamentScore, AssessmentReport
from app.models.instrument import AssessmentVersion

router = APIRouter()


@router.get("/my-history")
def get_user_assessment_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieve all completed assessments for the authenticated user."""
    sessions = db.scalars(
        select(AssessmentSession)
        .where(
            AssessmentSession.user_id == str(current_user.id),
            AssessmentSession.status == "completed"
        )
        .order_by(AssessmentSession.completed_at.desc())
    ).all()

    items = []
    for s in sessions:
        ver = db.get(AssessmentVersion, s.version_id)
        scores = db.scalars(
            select(TemperamentScore).where(TemperamentScore.session_id == s.id)
        ).all()
        report = db.scalar(
            select(AssessmentReport).where(AssessmentReport.session_id == s.id)
        )

        items.append({
            "session_id": s.id,
            "instrument": ver.instrument if ver else "unknown",
            "version": ver.version if ver else "unknown",
            "completed_at": s.completed_at,
            "scores": [
                {
                    "dimension": sc.dimension,
                    "score": float(sc.score) if sc.score is not None else None,
                    "confidence": float(sc.confidence),
                }
                for sc in scores
            ],
            "report_id": report.id if report else None,
        })

    return {"user_id": current_user.id, "count": len(items), "history": items}


@router.get("/compare/{session_id_1}/{session_id_2}")
def compare_sessions(
    session_id_1: uuid.UUID,
    session_id_2: uuid.UUID,
    db: Session = Depends(get_db)
):
    """Compare two completed assessment sessions, checking instrument version compatibility."""
    s1 = db.get(AssessmentSession, session_id_1)
    s2 = db.get(AssessmentSession, session_id_2)

    if not s1 or not s2:
        raise HTTPException(status_code=404, detail="One or both sessions not found.")

    v1 = db.get(AssessmentVersion, s1.version_id)
    v2 = db.get(AssessmentVersion, s2.version_id)

    # Check comparability
    comparable = (v1 and v2 and v1.instrument == v2.instrument and v1.version == v2.version)

    scores1 = {
        sc.dimension: float(sc.score) if sc.score is not None else None
        for sc in db.scalars(select(TemperamentScore).where(TemperamentScore.session_id == s1.id)).all()
    }
    scores2 = {
        sc.dimension: float(sc.score) if sc.score is not None else None
        for sc in db.scalars(select(TemperamentScore).where(TemperamentScore.session_id == s2.id)).all()
    }

    comparison = {}
    all_dims = set(scores1.keys()).union(scores2.keys())
    for d in all_dims:
        sc1 = scores1.get(d)
        sc2 = scores2.get(d)
        delta = round(sc2 - sc1, 1) if (sc1 is not None and sc2 is not None) else None
        comparison[d] = {
            "session_1": sc1,
            "session_2": sc2,
            "delta": delta,
        }

    return {
        "session_1": {"id": s1.id, "version": v1.version if v1 else None, "date": s1.completed_at},
        "session_2": {"id": s2.id, "version": v2.version if v2 else None, "date": s2.completed_at},
        "comparable_with_previous": comparable,
        "note": "Instruments versions match; comparisons valid." if comparable else "Warning: Versions differ; interpret score shifts with caution.",
        "dimensions": comparison,
    }
