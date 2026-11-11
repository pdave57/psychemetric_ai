from typing import TypedDict,Optional
class AssessmentState(TypedDict,total=False):
    user_id:str
    session_id:int
    current_domain:str
    current_question:Optional[str]
    answers:list[dict]
    temperament_scores:dict
    emotional_patterns:dict
    questions_asked:int
    confidence:float
    safety_flags:list[str]
    assessment_complete:bool
    final_report:Optional[dict]
