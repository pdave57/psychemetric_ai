"""Reports routes: retrieve a persisted assessment report."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import AssessmentReport

router = APIRouter()


@router.get("/{report_id}")
def get_report(report_id: uuid.UUID, db: Session = Depends(get_db)):
    report = db.get(AssessmentReport, report_id)
    if not report:
        raise HTTPException(404, "Report not found")
    return {
        "id":           report.id,
        "session_id":   report.session_id,
        "structured":   report.structured,
        "narrative":    report.narrative,
        "created_at":   report.created_at,
    }
