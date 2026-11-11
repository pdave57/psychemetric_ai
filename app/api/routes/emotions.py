from fastapi import APIRouter,Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.emotion import EmotionSelfReportRequest
from app.services.emotion_service import record_emotion_self_report
router=APIRouter()
@router.post("/sessions/{session_id}")
def create(session_id:int,payload:EmotionSelfReportRequest,db:Session=Depends(get_db)):
    x=record_emotion_self_report(db,session_id,payload)
    return {"id":x.id,"session_id":x.session_id,"emotion":x.emotion,"intensity":x.intensity,"status":"recorded_as_self_report"}
