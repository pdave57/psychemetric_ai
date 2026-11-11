from pydantic import BaseModel
class AnswerOptionOut(BaseModel):
    value:int
    label:str
class QuestionOut(BaseModel):
    id:int
    code:str
    prompt:str
    dimension:str
    reverse_scored:bool
    display_order:int
    options:list[AnswerOptionOut]
