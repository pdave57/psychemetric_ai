"""Tests for the scoring engine.

Uses SimpleNamespace to simulate ORM objects — no database required.
Tests cover both the new ``loads``/``likert_value`` model and the
legacy ``dimension``/``raw_value`` attributes for backward compatibility.
"""

import pytest
from types import SimpleNamespace

from app.services.scoring_service import calculate_temperament_scores


# --- helpers ----------------------------------------------------------------

def q(i, d, rev=False, w=1, loads=None):
    """Build a question-like namespace for testing."""
    return SimpleNamespace(
        id=i,
        dimension=d,          # legacy attribute
        reverse_scored=rev,   # legacy attribute
        reverse_coded=rev,    # new attribute
        weight=w,
        loads=loads or {},    # new attribute; empty → scoring falls back to dimension
        area="default",
    )


def r(i, v):
    """Build a response-like namespace with both attribute names."""
    return SimpleNamespace(question_id=i, raw_value=v, likert_value=v)


# --- tests ------------------------------------------------------------------

def test_maximum_maps_to_100():
    assert calculate_temperament_scores([q(1, "sanguine")], [r(1, 5)])["sanguine"]["normalized_score"] == 100


def test_minimum_maps_to_zero():
    assert calculate_temperament_scores([q(1, "sanguine")], [r(1, 1)])["sanguine"]["normalized_score"] == 0


def test_reverse_scoring():
    result = calculate_temperament_scores([q(1, "phlegmatic", rev=True)], [r(1, 1)])
    assert result["phlegmatic"]["raw_mean"] == 5
    assert result["phlegmatic"]["normalized_score"] == 100


def test_missing_dimension_is_none():
    assert calculate_temperament_scores([], [])["melancholic"] is None


def test_weights_are_applied():
    result = calculate_temperament_scores(
        [q(1, "choleric", w=2), q(2, "choleric")],
        [r(1, 5), r(2, 1)],
    )
    assert result["choleric"]["raw_mean"] == pytest.approx(3.67, abs=0.01)


def test_loads_dict_routes_to_correct_dimension():
    """When ``loads`` is set, the item should score into the specified dimension."""
    question = SimpleNamespace(
        id=99, dimension=None, reverse_scored=False, reverse_coded=False,
        weight=1, loads={"sanguine": 1.0}, area="social",
    )
    result = calculate_temperament_scores([question], [r(99, 5)])
    assert result["sanguine"]["normalized_score"] == 100
