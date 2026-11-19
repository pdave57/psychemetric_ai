"""Emotion self-report, check-in, and contextual follow-up service.

Records a user's self-reported emotional state linked to an assessment session
or standalone check-in. Utilizes scoring parameters and clinical-safety guardrails
from the Assessment Knowledge Pack.

Construct Taxonomy
------------------
1. Temperament tendencies: Enduring baseline behavioral inclinations across 4 classical styles.
2. Emotional skills: Learned competencies (Self-Awareness, Self-Regulation, Motivation, Empathy, Social Skills).
3. Current emotional experiences: Transient, present-moment affective states and situational burden.
"""

import uuid
from decimal import Decimal
from typing import Dict, Any, List, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import AssessmentSession, EmotionAssessment, EmotionBand, EmotionalTrigger
from app.knowledge_pack import get_emotion_indicators_bank
from app.knowledge_pack.scoring import score_emotion_indicator


def get_construct_framework_info() -> Dict[str, Any]:
    """Return explicit definitions distinguishing the three core measurement constructs."""
    return {
        "framework": "PsychemetreAI Tripartite Reflective Assessment Framework",
        "constructs": {
            "temperament_tendencies": {
                "nature": "Trait / Dispositional",
                "definition": (
                    "Enduring baseline behavioral styles across four classical dimensions "
                    "(Sanguine, Choleric, Melancholic, Phlegmatic). Evaluates how a person habitually "
                    "engages socially, approaches tasks, reacts to obstacles, and maintains steadiness."
                ),
                "assessment_structure": "20 Likert items (5 per dimension across 5 distinct behavioural areas)",
                "stability": "Relatively stable over time; reflective of constitutional style."
            },
            "emotional_skills": {
                "nature": "Competency / Capability",
                "definition": (
                    "Learned emotional intelligence capacities across 5 domains (Self-Awareness, "
                    "Self-Regulation, Intrinsic Motivation, Empathy, Social Skills). Evaluates the ability "
                    "to recognize, regulate, harness, and navigate emotions in self and interpersonal dynamics."
                ),
                "assessment_structure": "15 Likert items (3 per competency domain)",
                "stability": "Malleable; developable through deliberate practice and self-reflection."
            },
            "current_emotional_experiences": {
                "nature": "State / Momentary Affect",
                "definition": (
                    "Transient, present-moment feelings, situational reactions, and acute emotional burden. "
                    "Evaluates what emotions are currently active, their perceived intensity, situational "
                    "triggers, and resulting cognitive or physical load."
                ),
                "assessment_structure": "Emotion check-in (selection of current emotions) + optional contextual follow-up",
                "stability": "Dynamic; fluctuates hour-by-hour and day-by-day based on circumstances."
            }
        }
    }


def generate_contextual_follow_up(selected_emotions: List[str]) -> List[Dict[str, Any]]:
    """Generate tailored, optional follow-up questions for the selected emotions."""
    bank = get_emotion_indicators_bank()
    emotion_map = {e["code"]: e for e in bank.get("emotions", [])}

    follow_ups = []
    for code in selected_emotions:
        info = emotion_map.get(code)
        label = info.get("label", code.capitalize()) if info else code.capitalize()
        triggers = info.get("common_triggers", []) if info else []
        adaptive = info.get("adaptive_responses", []) if info else []

        # 1. Subjective intensity (0–10)
        follow_ups.append({
            "emotion": code,
            "question_id": f"intensity_{code}",
            "question_text": f"How intensely are you feeling {label} right now (0 = barely noticeable, 10 = overwhelming)?",
            "kind": "scale_10",
            "options": [str(i) for i in range(11)],
            "common_triggers": triggers,
            "adaptive_options": adaptive,
            "is_optional": True,
        })

        # 2. Situational trigger exploration
        follow_ups.append({
            "emotion": code,
            "question_id": f"trigger_{code}",
            "question_text": f"What specific situation, interaction, or thought contributed to this {label}?",
            "kind": "choice",
            "options": [t.replace("_", " ").capitalize() for t in triggers] + ["Other / Personal trigger"],
            "common_triggers": triggers,
            "adaptive_options": adaptive,
            "is_optional": True,
        })

        # 3. Typical duration / lingering pattern
        follow_ups.append({
            "emotion": code,
            "question_id": f"duration_{code}",
            "question_text": f"How long has this {label} been present, or how long does it usually linger?",
            "kind": "choice",
            "options": ["minutes", "hours", "days", "weeks", "varies"],
            "common_triggers": triggers,
            "adaptive_options": adaptive,
            "is_optional": True,
        })

    return follow_ups


def record_emotion_check_in(db: Session, payload) -> Dict[str, Any]:
    """Record an emotion check-in and generate optional contextual follow-up questions."""
    check_in_id = str(uuid.uuid4())
    selected = payload.selected_emotions
    follow_up_questions = generate_contextual_follow_up(selected)

    return {
        "check_in_id": check_in_id,
        "user_id": payload.user_id,
        "session_id": payload.session_id,
        "selected_emotions": selected,
        "construct_type": "current_emotional_experiences",
        "contextual_follow_up_questions": follow_up_questions,
        "message": (
            f"Check-in recorded for {len(selected)} emotion(s). "
            "You may optionally answer the contextual follow-up questions below to reflect on intensity and triggers."
        ),
    }


def record_contextual_follow_up(db: Session, payload) -> Dict[str, Any]:
    """Persist responses to optional contextual follow-up questions."""
    session_id = payload.session_id
    if session_id and not db.get(AssessmentSession, session_id):
        raise HTTPException(404, "Session not found")

    saved_items = []
    bank = get_emotion_indicators_bank()
    emotion_map = {e["code"]: e for e in bank.get("emotions", [])}

    for ans in payload.answers:
        emotion_code = ans.emotion
        intensity = ans.intensity if ans.intensity is not None else 5
        frequency = ans.frequency or "sometimes"
        duration = ans.duration or "hours"
        impact = ans.impact or "none"

        scored = score_emotion_indicator(
            frequency_val=frequency,
            intensity=intensity,
            duration_val=duration,
            impact_val=impact,
        )
        burden_index = Decimal(str(scored["burden_index"]))
        band = EmotionBand(scored["band"])

        row_id = None
        if session_id:
            row = EmotionAssessment(
                session_id=session_id,
                emotion=emotion_code,
                frequency=frequency,
                intensity=intensity,
                duration=duration,
                impact=impact,
                burden_index=burden_index,
                band=band,
                trigger=ans.trigger,
                response=ans.coping_strategy,
                source="contextual_follow_up",
            )
            db.add(row)
            db.flush()
            row_id = row.id

            if ans.trigger:
                db.add(EmotionalTrigger(
                    emotion_assessment_id=row.id,
                    trigger_code=ans.trigger,
                ))
            db.commit()

        info = emotion_map.get(emotion_code, {})
        saved_items.append({
            "id": row_id,
            "emotion": emotion_code,
            "intensity": intensity,
            "burden_index": float(burden_index),
            "band": band.value,
            "recommended_coping": info.get("adaptive_responses", []),
            "recorded": True,
        })

    return {
        "status": "completed",
        "construct": "current_emotional_experiences",
        "user_id": payload.user_id,
        "session_id": session_id,
        "processed_emotions": saved_items,
    }


def record_emotion_self_report(db: Session, session_id, payload):
    """Persist a single emotional self-report (backwards compatible)."""
    if not db.get(AssessmentSession, session_id):
        raise HTTPException(404, "Session not found")

    data = payload.model_dump()
    trigger_text = data.pop("trigger", None)

    scored = score_emotion_indicator(
        frequency_val=data["frequency"],
        intensity=data["intensity"],
        duration_val=data["duration"],
        impact_val=data.get("impact", "none") or "none",
    )
    burden_index = Decimal(str(scored["burden_index"]))
    band = EmotionBand(scored["band"])

    row = EmotionAssessment(
        session_id=session_id,
        burden_index=burden_index,
        band=band,
        source="structured",
        **data,
    )
    db.add(row)
    db.flush()

    if trigger_text:
        db.add(EmotionalTrigger(
            emotion_assessment_id=row.id,
            trigger_code=trigger_text,
        ))

    db.commit()
    db.refresh(row)
    return row
