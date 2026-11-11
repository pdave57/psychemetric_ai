from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base

class Question(Base):
    __tablename__="questions"
    id:Mapped[int]=mapped_column(primary_key=True)
    instrument_id:Mapped[int]=mapped_column(ForeignKey("assessment_instruments.id"))
    code:Mapped[str]=mapped_column(String(40))
    prompt:Mapped[str]=mapped_column(Text)
    dimension:Mapped[str]=mapped_column(String(30))
    reverse_scored:Mapped[bool]=mapped_column(Boolean,default=False)
    required:Mapped[bool]=mapped_column(Boolean,default=True)
    weight:Mapped[float]=mapped_column(Float,default=1.0)
    display_order:Mapped[int]=mapped_column(Integer)

class AnswerOption(Base):
    __tablename__="answer_options"
    id:Mapped[int]=mapped_column(primary_key=True)
    question_id:Mapped[int]=mapped_column(ForeignKey("questions.id"))
    label:Mapped[str]=mapped_column(String(100))
    value:Mapped[int]=mapped_column(Integer)
    
class UserResponse(Base):
    __tablename__="user_responses"
    __table_args__=(UniqueConstraint("session_id","question_id",name="uq_session_question"),)
    id:Mapped[int]=mapped_column(primary_key=True)
    session_id:Mapped[int]=mapped_column(ForeignKey("assessment_sessions.id"))
    question_id:Mapped[int]=mapped_column(ForeignKey("questions.id"))
    raw_value:Mapped[int]=mapped_column(Integer)
    answered_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
