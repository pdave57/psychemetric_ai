from sqlalchemy import select

from app.models import AssessmentInstrument, AssessmentSession, Question, AnswerOption, UserResponse

ITEMS=[
("SAN01","I feel energised when interacting with a group of people.","sanguine",False),
("SAN02","I readily express excitement when something interests me.","sanguine",False),
("SAN03","I enjoy spontaneous social activities.","sanguine",False),
("SAN04","I usually prefer to keep to myself at social gatherings.","sanguine",True),
("CHO01","I am comfortable taking the lead when a decision is needed.","choleric",False),
("CHO02","I make decisions promptly when I have enough information.","choleric",False),
("CHO03","I set challenging goals and work persistently toward them.","choleric",False),
("CHO04","I avoid taking responsibility when a group needs direction.","choleric",True),
("MEL01","I think carefully about details before completing a task.","melancholic",False),
("MEL02","I reflect on my experiences to understand what went well or badly.","melancholic",False),
("MEL03","I notice small errors or inconsistencies in my work.","melancholic",False),
("MEL04","I rarely think through the possible consequences of my decisions.","melancholic",True),
("PHL01","I remain patient when other people disagree with me.","phlegmatic",False),
("PHL02","I prefer to resolve disagreements calmly.","phlegmatic",False),
("PHL03","People can generally rely on me to be steady and consistent.","phlegmatic",False),
("PHL04","I become impatient quickly when plans change.","phlegmatic",True)]
OPTIONS=[(1,"Strongly disagree"),(2,"Disagree"),(3,"Neither agree nor disagree"),(4,"Agree"),(5,"Strongly agree")]

def seed_initial_instrument(db):
    obj=db.scalar(select(AssessmentInstrument).where(AssessmentInstrument.code=="innermap_temperament",AssessmentInstrument.version=="0.1.0"))
    if obj:return obj
    obj=AssessmentInstrument(code="innermap_temperament",version="0.1.0",title="InnerMap Reflective Temperament Questionnaire",description="Prototype only.",status="prototype")
    db.add(obj);db.flush()
    for n,(code,prompt,dimension,reverse) in enumerate(ITEMS,1):
        q=Question(instrument_id=obj.id,code=code,prompt=prompt,dimension=dimension,reverse_scored=reverse,required=True,weight=1.0,display_order=n)
        db.add(q);db.flush()
        db.add_all([AnswerOption(question_id=q.id,value=v,label=l) for v,l in OPTIONS])
    db.commit();return obj

def get_instrument(db,code,version):
    return db.scalar(select(AssessmentInstrument).where(AssessmentInstrument.code==code,AssessmentInstrument.version==version))

def create_session(db,user_id,instrument):
    s=AssessmentSession(user_id=user_id,instrument_id=instrument.id);db.add(s);db.commit();db.refresh(s);return s

def get_questions(db,instrument_id):
    return db.scalars(select(Question).where(Question.instrument_id==instrument_id).order_by(Question.display_order)).all()

def get_options(db,question_id):
    return db.scalars(select(AnswerOption).where(AnswerOption.question_id==question_id).order_by(AnswerOption.value)).all()

def get_responses(db,session_id):
    return db.scalars(select(UserResponse).where(UserResponse.session_id==session_id)).all()

def save_response(db,session_id,question_id,value):
    r=db.scalar(select(UserResponse).where(UserResponse.session_id==session_id,UserResponse.question_id==question_id))
    if r:r.raw_value=value
    else:r=UserResponse(session_id=session_id,question_id=question_id,raw_value=value);db.add(r)
    db.commit();return r
