from typing import Literal
from pydantic import BaseModel, Field
class EmotionSelfReportRequest(BaseModel):
    emotion:Literal["anger","anxiety","fear","sadness","stress","guilt","jealousy","loneliness","joy"]
    frequency:Literal["rarely","sometimes","often","very_often"]
    intensity:int=Field(ge=0,le=10)
    duration:Literal["minutes","hours","days","weeks","varies"]
    trigger:str|None=Field(default=None,max_length=1000)
    response:str|None=Field(default=None,max_length=1000)
    coping_strategy:str|None=Field(default=None,max_length=1000)
    impact:str|None=Field(default=None,max_length=1000)
