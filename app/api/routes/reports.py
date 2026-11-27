"""Reports routes: retrieve a persisted assessment report and export PDF."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.core.database import get_db, run_sync
from app.models.result import AssessmentReport
from app.services.pdf_service import generate_assessment_pdf

router = APIRouter()


@router.get("/{report_id}")
async def get_report(report_id: uuid.UUID, db: Session = Depends(get_db)):
    report = await run_sync(db.get, AssessmentReport, report_id)
    if not report:
        raise HTTPException(404, "Report not found")
    return {
        "id":           report.id,
        "session_id":   report.session_id,
        "structured":   report.structured,
        "narrative":    report.narrative,
        "created_at":   report.created_at,
    }


@router.get("/{report_id}/pdf")
async def get_report_pdf(report_id: uuid.UUID, db: Session = Depends(get_db)):
    """Generate and download a self-contained PDF format assessment report."""
    report = await run_sync(db.get, AssessmentReport, report_id)
    if not report:
        raise HTTPException(404, "Report not found")

    structured = report.structured or {}
    narrative_text = (report.narrative or {}).get("narrative", "")

    pdf_payload = {
        "session_id": str(report.session_id),
        "temperament_scores": structured.get("temperament_scores", []),
        "narrative": narrative_text,
    }

    pdf_bytes = await run_sync(generate_assessment_pdf, pdf_payload)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=psychemetre_report_{report.session_id}.pdf"}
    )
