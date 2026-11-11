from datetime import datetime, timezone
from sqlalchemy import DateTime, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base
def now(): return datetime.now(timezone.utc)
class AssessmentInstrument(Base):
    __tablename__="assessment_instruments"
    __table_args__=(UniqueConstraint("code","version",name="uq_instrument_code_version"),)
    id:Mapped[int]=mapped_column(primary_key=True)
    code:Mapped[str]=mapped_column(String(80),index=True)
    version:Mapped[str]=mapped_column(String(20))
    title:Mapped[str]=mapped_column(String(200))
    description:Mapped[str]=mapped_column(Text,default="")
    status:Mapped[str]=mapped_column(String(20),default="prototype")
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class AssessmentSession(Base):
    __tablename__="assessment_sessions"
    id:Mapped[int]=mapped_column(primary_key=True)
    user_id:Mapped[str]=mapped_column(String(100),index=True)
    instrument_id:Mapped[int]=mapped_column(ForeignKey("assessment_instruments.id"))
    status:Mapped[str]=mapped_column(String(20),default="in_progress")
    started_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    completed_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
class TemperamentScore(Base):
    __tablename__="temperament_scores"
    __table_args__=(UniqueConstraint("session_id","dimension",name="uq_session_dimension"),)
    id:Mapped[int]=mapped_column(primary_key=True)
    session_id:Mapped[int]=mapped_column(ForeignKey("assessment_sessions.id"))
    dimension:Mapped[str]=mapped_column(String(30))
    raw_mean:Mapped[float]=mapped_column(Float)
    normalized_score:Mapped[float]=mapped_column(Float)
    scoring_version:Mapped[str]=mapped_column(String(30))
    interpretation:Mapped[str]=mapped_column(Text)
