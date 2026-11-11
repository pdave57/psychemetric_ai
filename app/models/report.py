from datetime import datetime, timezone
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

class EmotionSelfAssessment(Base):
    __tablename__="emotion_self_assessments"
    
    id:Mapped[int]=mapped_column(primary_key=True)
    session_id:Mapped[int]=mapped_column(ForeignKey("assessment_sessions.id"))
    emotion:Mapped[str]=mapped_column(String(40))
    frequency:Mapped[str]=mapped_column(String(30))
    intensity:Mapped[int]=mapped_column(Integer)
    duration:Mapped[str]=mapped_column(String(40))
    trigger:Mapped[str|None]=mapped_column(Text,nullable=True)
    response:Mapped[str|None]=mapped_column(Text,nullable=True)
    coping_strategy:Mapped[str|None]=mapped_column(Text,nullable=True)
    impact:Mapped[str|None]=mapped_column(Text,nullable=True)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
