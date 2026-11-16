import pytest
from app.knowledge_pack.scoring import (
    score_likert_dimension, score_temperaments,
    score_emotional_intelligence, score_emotion_indicator
)
from app.knowledge_pack.validation import validate_answer

def test_likert_score_and_reverse_key():
    result = score_likert_dimension([5, 1], [False, True], minimum_answers=2)
    assert result["score"] == 100.0

def test_incomplete_dimension_is_not_zero():
    result = score_likert_dimension([5], [False], minimum_answers=2)
    assert result["status"] == "incomplete"
    assert result["score"] is None

def test_temperament_score_requires_minimum_items():
    result = score_temperaments({"sanguine":[4]*8, "choleric":[4]*8,
                                 "melancholic":[4]*8, "phlegmatic":[4]*7})
    assert result["status"] == "partial"

def test_emotion_indicator():
    result = score_emotion_indicator(2, 3, "several hours", 2)
    assert result["status"] == "complete"
    assert 0 <= result["score"] <= 100

def test_invalid_likert_rejected():
    with pytest.raises(ValueError):
        score_likert_dimension([6])

def test_answer_validation():
    q = {"response_type":"likert_5"}
    validate_answer(q, 4)
    with pytest.raises(ValueError):
        validate_answer(q, 8)
