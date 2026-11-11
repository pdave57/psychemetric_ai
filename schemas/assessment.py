from pydantic import BaseModel, Field

class AssessmentStartRequest(BaseModel):
    user_id:str=Field(min_length=1,max_length=100)
    instrument_code:str="innermap_temperament"
    instrument_version:str="0.1.0"
    
class AnswerSubmitRequest(BaseModel):
    question_id:int
    value:int=Field(ge=1,le=5)
