from fastapi import FastAPI
from app.core.database import Base, engine, SessionLocal
from app.repositories.assessment_repository import seed_initial_instrument
from app.api.routes import auth, assessments, questions, emotions, reports, recommendations
from app.core.logging import configure_logging

configure_logging()
app = FastAPI(title="InnerMap AI Assessment API", version="0.1.0",
 description="Reflective temperament assessment and emotional self-report prototype; not diagnostic.")
@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try: seed_initial_instrument(db)
    finally: db.close()
for route, prefix, tag in [
 (auth.router,"/api/v1/auth","Authentication"),
 (assessments.router,"/api/v1/assessments","Assessments"),
 (questions.router,"/api/v1/questions","Questions"),
 (emotions.router,"/api/v1/emotions","Emotional self-reports"),
 (reports.router,"/api/v1/reports","Reports"),
 (recommendations.router,"/api/v1/recommendations","Recommendations")]:
    app.include_router(route,prefix=prefix,tags=[tag])
@app.get("/health")
def health(): return {"status":"ok"}
