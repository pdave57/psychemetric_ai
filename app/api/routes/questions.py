from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models import AssessmentSession
from app.repositories.assessment_repository import get_questions,get_options
router=APIRouter()
@router.get("/sessions/{session_id}")
def questions(session_id:int,db:Session=Depends(get_db)):
    s=db.get(AssessmentSession,session_id)
    if not s:raise HTTPException(404,"Session not found")
    return [{"id":q.id,"code":q.code,"prompt":q.prompt,"dimension":q.dimension,"reverse_scored":q.reverse_scored,"display_order":q.display_order,"options":[{"value":o.value,"label":o.label} for o in get_options(db,q.id)]} for q in get_questions(db,s.instrument_id)]
