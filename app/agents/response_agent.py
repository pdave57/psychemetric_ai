"""User response evaluation, input validation, and emotion signal extractor agent.

Validates Likert answer values (1–5 scale bounds), preserves respondent response
fidelity, and performs emotion evidence extraction from accompanying qualitative
text without making clinical disorder assertions.
"""

import re
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from app.agents.state import AssessmentGraphState

_EMOTION_KEYWORDS = {
    "anxiety": ["anxious", "nervous", "worry", "worried", "uneasy", "tense", "panic"],
    "stress": ["stressed", "overwhelmed", "pressure", "burnout", "burdened"],
    "joy": ["happy", "energised", "energized", "excited", "joyful", "enthusiastic"],
    "calm": ["calm", "peaceful", "relaxed", "composed", "tranquil", "steady"],
    "sadness": ["sad", "down", "gloomy", "heavy-hearted", "disappointed"],
    "anger": ["angry", "frustrated", "irritated", "annoyed", "bitter"],
}


def validate_answer_value(val: Any) -> Optional[int]:
    """Validate and cast a Likert answer to an integer in [1, 5]."""
    if val is None:
        return None
    try:
        int_val = int(val)
        if 1 <= int_val <= 5:
            return int_val
    except (ValueError, TypeError):
        pass
    return None


def extract_emotion_signals(text: Optional[str]) -> List[Dict[str, Any]]:
    """Extract qualitative emotional states mentioned in free text without clinical claims."""
    if not text:
        return []

    signals = []
    lower = text.lower()

    for emotion, keywords in _EMOTION_KEYWORDS.items():
        matched = [k for k in keywords if re.search(rf"\b{re.escape(k)}\b", lower)]
        if matched:
            signals.append({
                "emotion": emotion,
                "confidence": 0.85,
                "keywords": matched,
                "source": "free_text",
            })

    return signals


def response_agent_node(state: AssessmentGraphState) -> Dict[str, Any]:
    """Response evaluation node.

    Processes pending user answer or incoming message, validates Likert range,
    extracts emotion signals, and appends to the answers ledger.
    """
    answers = list(state.get("answers", []))
    pending_q = state.get("pending_question")

    last_msg = state.get("last_user_message")
    extracted_emotions = list(state.get("extracted_emotions", []))

    if last_msg:
        new_signals = extract_emotion_signals(last_msg)
        extracted_emotions.extend(new_signals)

    # If the state has an uncommitted latest answer, validate and finalize it
    if answers:
        latest = answers[-1]
        raw_val = latest.get("value")
        valid_val = validate_answer_value(raw_val)
        if valid_val is not None:
            latest["value"] = valid_val
            latest["validated"] = True
            latest["timestamp"] = datetime.now(timezone.utc).isoformat()

        # Extract emotions from latest free_text if present
        text_val = latest.get("free_text") or latest.get("text")
        if text_val:
            new_signals = extract_emotion_signals(text_val)
            extracted_emotions.extend(new_signals)

    return {
        "answers": answers,
        "extracted_emotions": extracted_emotions,
        "pending_question": None,
        "phase": "planning",
        "interrupted": False,
    }
