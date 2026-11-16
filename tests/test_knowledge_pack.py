"""Tests for the complete Assessment Knowledge Pack."""

import pytest
from app.knowledge_pack import (
    get_answer_options,
    get_temperament_bank,
    get_emotional_intelligence_bank,
    get_emotion_indicators_bank,
    get_scoring_metadata,
    get_recommendation_rules,
)
from app.knowledge_pack.scoring import (
    score_likert_dimension,
    score_temperaments,
    score_emotional_intelligence,
    score_emotion_indicator,
)
from app.knowledge_pack.validation import validate_answer


def test_temperament_bank_integrity():
    bank = get_temperament_bank()
    assert bank["total_items"] == 40
    assert len(bank["questions"]) == 40

    # Exactly 10 items per dimension
    counts = {}
    for q in bank["questions"]:
        dim = q["dimension"]
        counts[dim] = counts.get(dim, 0) + 1
        assert "text" in q and len(q["text"]) > 10
        assert "code" in q
        assert isinstance(q["reverse_coded"], bool)

    for dim in ["sanguine", "choleric", "melancholic", "phlegmatic"]:
        assert counts[dim] == 10, f"Expected 10 items for {dim}, found {counts.get(dim)}"


def test_emotional_intelligence_bank_integrity():
    bank = get_emotional_intelligence_bank()
    assert bank["total_items"] == 25
    assert len(bank["questions"]) == 25

    # Exactly 5 items per dimension
    counts = {}
    for q in bank["questions"]:
        dim = q["dimension"]
        counts[dim] = counts.get(dim, 0) + 1
        assert "text" in q and len(q["text"]) > 10
        assert "code" in q
        assert isinstance(q["reverse_coded"], bool)

    expected_dims = ["self_awareness", "self_regulation", "intrinsic_motivation", "empathy", "social_skills"]
    for dim in expected_dims:
        assert counts[dim] == 5, f"Expected 5 items for {dim}, found {counts.get(dim)}"


def test_emotion_indicators_bank_integrity():
    bank = get_emotion_indicators_bank()
    assert len(bank["emotions"]) == 9
    emotions = [e["code"] for e in bank["emotions"]]
    expected = ["anger", "anxiety", "fear", "sadness", "stress", "guilt", "jealousy", "loneliness", "joy"]
    assert set(emotions) == set(expected)

    for e in bank["emotions"]:
        assert len(e["common_triggers"]) >= 3
        assert len(e["adaptive_responses"]) >= 2


def test_answer_options_structure():
    opts = get_answer_options()
    assert "likert_5_agreement" in opts["scales"]
    assert len(opts["scales"]["likert_5_agreement"]["options"]) == 5
    assert "emotion_intensity" in opts["scales"]
    assert opts["scales"]["emotion_intensity"]["max_value"] == 10


def test_recommendation_rules_structure():
    rules = get_recommendation_rules()
    assert len(rules["rules"]) >= 8
    for r in rules["rules"]:
        assert "id" in r
        assert "body" in r
        assert "how" in r["body"] and len(r["body"]["how"]) >= 2
        assert "evidence" in r


def test_scoring_temperament_40_items():
    # Simulate full 40 items answered with 4s and 5s
    bank = get_temperament_bank()
    dim_answers = {"sanguine": [], "choleric": [], "melancholic": [], "phlegmatic": []}
    dim_revs = {"sanguine": [], "choleric": [], "melancholic": [], "phlegmatic": []}

    for q in bank["questions"]:
        dim = q["dimension"]
        dim_answers[dim].append(5)
        dim_revs[dim].append(q["reverse_coded"])

    scored = score_temperaments(dim_answers, dim_revs, minimum_answers_per_dim=8)
    assert scored["status"] == "complete"
    for dim in ["sanguine", "choleric", "melancholic", "phlegmatic"]:
        assert scored["dimensions"][dim]["status"] == "complete"
        assert scored["dimensions"][dim]["score"] is not None


def test_scoring_eq_25_items():
    bank = get_emotional_intelligence_bank()
    dom_answers = {}
    dom_revs = {}
    for q in bank["questions"]:
        dom = q["dimension"]
        dom_answers.setdefault(dom, []).append(4)
        dom_revs.setdefault(dom, []).append(q["reverse_coded"])

    scored = score_emotional_intelligence(dom_answers, dom_revs, minimum_answers_per_domain=3)
    assert scored["status"] == "complete"
    for dom in ["self_awareness", "self_regulation", "intrinsic_motivation", "empathy", "social_skills"]:
        assert scored["domains"][dom]["status"] == "complete"
        assert scored["domains"][dom]["score"] is not None
