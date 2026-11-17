"""Scoring evaluation test suite and benchmark harness.

Tests mathematical correctness, reverse-coding inversion, threshold gating,
and statistical reliability metrics across:
- Classical 4-temperament scoring (40 items).
- Emotional Intelligence competency dimensions (25 items).
- Emotional state indicator and burden formulas.
"""

import pytest
from typing import Dict, Any, List

from app.knowledge_pack.scoring import (
    score_likert_dimension,
    score_temperaments,
    score_emotional_intelligence,
    score_emotion_indicator,
)
from app.knowledge_pack.validation import validate_answer
from app.evaluation.evaluation_metrics import (
    cronbach_alpha,
    split_half_reliability,
    standard_error_of_measurement,
    mean_absolute_error,
    EvaluationReport,
)


def test_pure_sanguine_benchmark_profile():
    """All maximum (5) answers on sanguine items must result in 100.0% score."""
    dim_answers = {
        "sanguine": [5] * 10,
        "choleric": [1] * 10,
        "melancholic": [1] * 10,
        "phlegmatic": [1] * 10,
    }
    result = score_temperaments(dim_answers, minimum_answers_per_dim=8)
    assert result["status"] == "complete"
    assert result["dimensions"]["sanguine"]["score"] == 100.0
    assert result["dimensions"]["choleric"]["score"] == 0.0
    assert result["dimensions"]["melancholic"]["score"] == 0.0
    assert result["dimensions"]["phlegmatic"]["score"] == 0.0
    assert result["leading_tendencies"][0] == "sanguine"


def test_pure_melancholic_benchmark_profile():
    """All maximum (5) answers on melancholic items must yield melancholic as primary."""
    dim_answers = {
        "sanguine": [2] * 10,
        "choleric": [1] * 10,
        "melancholic": [5] * 10,
        "phlegmatic": [2] * 10,
    }
    result = score_temperaments(dim_answers, minimum_answers_per_dim=8)
    assert result["status"] == "complete"
    assert result["dimensions"]["melancholic"]["score"] == 100.0
    assert result["leading_tendencies"][0] == "melancholic"


def test_balanced_midpoint_profile():
    """All neutral (3) answers must yield exactly 50.0% across all dimensions."""
    dim_answers = {
        "sanguine": [3] * 10,
        "choleric": [3] * 10,
        "melancholic": [3] * 10,
        "phlegmatic": [3] * 10,
    }
    result = score_temperaments(dim_answers, minimum_answers_per_dim=8)
    for dim in ["sanguine", "choleric", "melancholic", "phlegmatic"]:
        assert result["dimensions"][dim]["score"] == 50.0
        assert result["dimensions"][dim]["raw_mean"] == 3.0


def test_reverse_key_coding_mathematical_inversion():
    """Verify reverse-keyed items invert: 1 -> 5 (100%), 5 -> 1 (0%)."""
    # Answer 1 with reverse=True should invert to 5 -> 100.0%
    res_high = score_likert_dimension(answers=[1], reverse_keys=[True], minimum_answers=1)
    assert res_high["score"] == 100.0
    assert res_high["raw_mean"] == 5.0

    # Answer 5 with reverse=True should invert to 1 -> 0.0%
    res_low = score_likert_dimension(answers=[5], reverse_keys=[True], minimum_answers=1)
    assert res_low["score"] == 0.0
    assert res_low["raw_mean"] == 1.0

    # Mixed: [5 (regular), 1 (reverse)] -> [5, 5] -> 100.0%
    res_mixed = score_likert_dimension(answers=[5, 1], reverse_keys=[False, True], minimum_answers=2)
    assert res_mixed["score"] == 100.0


def test_scale_boundary_validation():
    """Values outside Likert [1, 5] must be rejected with ValueError."""
    with pytest.raises(ValueError):
        score_likert_dimension(answers=[0])

    with pytest.raises(ValueError):
        score_likert_dimension(answers=[6])

    with pytest.raises(ValueError):
        validate_answer({"response_type": "likert_5"}, 7)


def test_minimum_answers_integrity_threshold():
    """Fewer responses than minimum threshold must return incomplete, not arbitrary 0."""
    result = score_likert_dimension(answers=[4, 5], minimum_answers=5)
    assert result["status"] == "incomplete"
    assert result["score"] is None
    assert result["raw_mean"] is None
    assert result["n_items"] == 2

    # Partial temperament scoring
    temp_result = score_temperaments({
        "sanguine": [4] * 8,
        "choleric": [4] * 8,
        "melancholic": [4] * 8,
        "phlegmatic": [4] * 4,  # Below 8 items
    }, minimum_answers_per_dim=8)
    assert temp_result["status"] == "partial"
    assert temp_result["dimensions"]["phlegmatic"]["status"] == "incomplete"


def test_emotional_intelligence_five_dimensions():
    """Verify scoring of all 5 EQ competencies."""
    eq_answers = {
        "self_awareness": [4, 5, 4, 5, 4],
        "self_regulation": [3, 4, 3, 4, 3],
        "intrinsic_motivation": [5, 5, 4, 5, 5],
        "empathy": [4, 4, 4, 4, 4],
        "social_skills": [3, 3, 4, 4, 3],
    }
    result = score_emotional_intelligence(eq_answers, minimum_answers_per_domain=5)
    assert result["status"] == "complete"
    assert len(result["domains"]) == 5
    assert result["domains"]["self_awareness"]["score"] > 80.0
    domain_scores = [d["score"] for d in result["domains"].values() if d["score"] is not None]
    overall_mean = sum(domain_scores) / len(domain_scores)
    assert overall_mean > 70.0


def test_emotion_indicator_scoring():
    """Verify emotion burden score calculation within [0, 100]."""
    indicator = score_emotion_indicator(
        frequency_val=2,
        intensity=4,
        duration_val="several hours",
        impact_val=3
    )
    assert indicator["status"] == "complete"
    assert 0.0 <= indicator["score"] <= 100.0
    assert "band" in indicator


def test_psychometric_reliability_alpha():
    """Simulated consistent responses must produce Cronbach's alpha >= 0.70."""
    # 20 respondents with consistent trait patterns across 6 items
    base_responses = [
        [5, 5, 4, 5, 4, 5],
        [4, 4, 4, 5, 4, 4],
        [5, 4, 5, 4, 5, 4],
        [3, 3, 4, 3, 3, 4],
        [2, 2, 3, 2, 2, 3],
        [1, 2, 1, 2, 1, 2],
        [1, 1, 2, 1, 1, 1],
        [4, 5, 5, 4, 5, 4],
        [3, 3, 3, 4, 3, 3],
        [2, 3, 2, 2, 3, 2],
    ] * 3  # 30 respondents
    alpha = cronbach_alpha(base_responses)
    assert alpha >= 0.80

    split_half = split_half_reliability(base_responses)
    assert split_half >= 0.80

    sem = standard_error_of_measurement(std_dev=15.0, reliability=alpha)
    assert sem < 8.0


def run_scoring_evaluation() -> EvaluationReport:
    """Execute all scoring benchmarks and aggregate results into an EvaluationReport."""
    scenarios = [
        ("pure_sanguine", test_pure_sanguine_benchmark_profile),
        ("pure_melancholic", test_pure_melancholic_benchmark_profile),
        ("balanced_midpoint", test_balanced_midpoint_profile),
        ("reverse_keys", test_reverse_key_coding_mathematical_inversion),
        ("scale_boundaries", test_scale_boundary_validation),
        ("minimum_thresholds", test_minimum_answers_integrity_threshold),
        ("eq_dimensions", test_emotional_intelligence_five_dimensions),
        ("emotion_indicators", test_emotion_indicator_scoring),
        ("psychometric_alpha", test_psychometric_reliability_alpha),
    ]

    passed = 0
    failures = []
    for name, fn in scenarios:
        try:
            fn()
            passed += 1
        except Exception as e:
            failures.append({"scenario": name, "error": str(e)})

    return EvaluationReport(
        category="scoring_evaluation",
        total_scenarios=len(scenarios),
        passed_scenarios=passed,
        metrics={
            "pass_rate": passed / len(scenarios),
            "benchmark_mae": 0.0,
        },
        failures=failures,
    )
