from app.repositories.assessment_repository import seed_initial_instrument,create_session
from app.schemas.emotion import EmotionSelfReportRequest
from app.services.emotion_service import record_emotion_self_report
def test_emotion_persists_as_self_report(db):
    instrument=seed_initial_instrument(db);session=create_session(db,"u1",instrument)
    payload=EmotionSelfReportRequest(emotion="stress",frequency="often",intensity=7,duration="hours",trigger="Deadlines")
    saved=record_emotion_self_report(db,session.id,payload)
    assert saved.emotion=="stress" and saved.intensity==7
