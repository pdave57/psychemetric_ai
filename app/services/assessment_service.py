from datetime import datetime,timezone
from fastapi import HTTPException
from sqlalchemy import select
from app.models import AssessmentInstrument,Question,AnswerOption,TemperamentScore
from app.repositories import assessment_repository as repo
from app.services.scoring_service import calculate_temperament_scores,describe_score,SCORING_VERSION,DIMENSIONS
DISCLAIMER="Classical temperaments are used as a reflective framework, not validated diagnoses. Scores are not clinical diagnoses or predictions. Emotional information is self-reported, not a clinical assessment."
def start_assessment(db,user_id,code,version):
    instrument=repo.get_instrument(db,code,version)
    if not instrument:raise HTTPException(404,"Instrument version not found")
    session=repo.create_session(db,user_id,instrument)
    return session,repo.get_questions(db,instrument.id)
def submit_answer(db,session_id,question_id,value):
    s=db.get(repo.AssessmentSession,session_id)
    if not s:raise HTTPException(404,"Session not found")
    if s.status!="in_progress":raise HTTPException(409,"Assessment is not in progress")
    q=db.get(Question,question_id)
    if not q or q.instrument_id!=s.instrument_id:raise HTTPException(400,"Question does not belong to this instrument")
    valid=db.scalar(select(AnswerOption.id).where(AnswerOption.question_id==question_id,AnswerOption.value==value))
    if not valid:raise HTTPException(422,"Invalid answer option")
    repo.save_response(db,session_id,question_id,value)
    return {"saved":True,"session_id":session_id,"question_id":question_id}
def complete_assessment(db,session_id):
    s=db.get(repo.AssessmentSession,session_id)
    if not s:raise HTTPException(404,"Session not found")
    if s.status!="in_progress":raise HTTPException(409,"Assessment is not in progress")
    instrument=db.get(AssessmentInstrument,s.instrument_id)
    qs=repo.get_questions(db,s.instrument_id);rs=repo.get_responses(db,session_id)
    answered={r.question_id for r in rs}
    missing=[q.code for q in qs if q.required and q.id not in answered]
    if missing:raise HTTPException(422,detail={"message":"Required answers are missing","missing_question_codes":missing})
    values=calculate_temperament_scores(qs,rs);output=[];leaders=[]
    for d in DIMENSIONS:
        v=values[d]
        if v is None:continue
        desc=describe_score(v["normalized_score"])
        output.append({"dimension":d,**v,"interpretation":desc})
        db.add(TemperamentScore(session_id=session_id,dimension=d,raw_mean=v["raw_mean"],normalized_score=v["normalized_score"],scoring_version=SCORING_VERSION,interpretation=desc))
    db.flush()
    s.status="completed";s.completed_at=datetime.now(timezone.utc);db.commit()
    leaders=sorted(output,key=lambda x:x["normalized_score"],reverse=True)
    return {"session_id":session_id,"instrument":instrument.code,"instrument_version":instrument.version,"scoring_version":SCORING_VERSION,"status":"completed","temperament_scores":output,"leading_tendencies":[x["dimension"] for x in leaders[:2]],"disclaimer":DISCLAIMER}
