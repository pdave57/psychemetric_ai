from fastapi import HTTPException
from app.models import AssessmentSession,EmotionSelfAssessment
def record_emotion_self_report(db,session_id,payload):
    if not db.get(AssessmentSession,session_id):raise HTTPException(404,"Session not found")
    row=EmotionSelfAssessment(session_id=session_id,**payload.model_dump())
    db.add(row);db.commit();db.refresh(row);return row
