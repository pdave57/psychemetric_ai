"""Assessment Knowledge Pack loader and registry.

Provides typed access to:
- 40 Temperament Items (10 per dimension: Sanguine, Choleric, Melancholic, Phlegmatic)
- 25 Emotional Intelligence Items (5 per domain: Self-Awareness, Self-Regulation, Motivation, Empathy, Social Skills)
- 9 Emotion Discrete Indicators (Anger, Anxiety, Fear, Sadness, Stress, Guilt, Jealousy, Loneliness, Joy)
- Standard response option scales (Likert 5, Likert 7, Frequency, Duration, Intensity)
- Scoring configurations and minimum item thresholds
- Recommendation decision rules and evidence mapping
"""

import json
from pathlib import Path
from typing import Dict, Any, List

_PACK_DIR = Path(__file__).resolve().parent

def load_json(filename: str) -> Dict[str, Any]:
    with open(_PACK_DIR / filename, "r", encoding="utf-8") as f:
        return json.load(f)

def get_answer_options() -> Dict[str, Any]:
    return load_json("answer_options.json")

def get_temperament_bank() -> Dict[str, Any]:
    return load_json("temperament_bank.json")

def get_temperament_20_bank() -> Dict[str, Any]:
    return load_json("temperament_20_bank.json")

def get_temperament_40_bank() -> Dict[str, Any]:
    return load_json("temperament_40_bank.json")

def get_emotional_intelligence_bank() -> Dict[str, Any]:
    return load_json("emotional_intelligence_15_bank.json")

def get_emotional_intelligence_15_bank() -> Dict[str, Any]:
    return load_json("emotional_intelligence_15_bank.json")

def get_emotional_intelligence_25_bank() -> Dict[str, Any]:
    return load_json("emotional_intelligence_25_bank.json")

def get_emotion_indicators_bank() -> Dict[str, Any]:
    return load_json("emotion_indicators_bank.json")

def get_scoring_metadata() -> Dict[str, Any]:
    return load_json("scoring_metadata.json")

def get_recommendation_rules() -> Dict[str, Any]:
    return load_json("recommendation_rules.json")
