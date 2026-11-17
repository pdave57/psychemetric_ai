"""Agent evaluation test suite and orchestrator benchmark.

Tests and evaluates:
1. LangGraph assessment state graph flow (transitions, questioning, interrupts, halting).
2. Mid-session safety halt on crisis disclosure.
3. Numeric consistency validator (detecting and replacing hallucinated scores).
4. Non-diagnostic tone guardrails (preventing clinical/disorder assertions).
5. Deterministic fallback generation under numeric discrepancy.
"""

import pytest
import uuid
from typing import Dict, Any, List

from app.agents.graph import (
    build_assessment_graph,
    safety_check_node,
    question_node,
    scoring_node,
    narrative_node,
    should_continue_router,
)
from app.services.narrative_service import (
    generate_narrative_report,
    validate_numeric_consistency,
    PROMPT_VERSION,
)
from app.core.llm import BaseLLM
from app.evaluation.evaluation_metrics import (
    numeric_consistency_score,
    diagnostic_claim_absence_score,
    EvaluationReport,
)


class MockLLM(BaseLLM):
    """Deterministic LLM for repeatable agent evaluation tests."""
    def __init__(self, response_text: str):
        self.response_text = response_text
        self.model = "MockLLM"

    def generate(self, prompt: str, system: str = "", max_tokens: int = 500) -> str:
        return self.response_text


def test_agent_graph_state_machine_questioning_flow():
    """Verify that graph routes through question sequence until completion."""
    initial_state = {
        "session_id": str(uuid.uuid4()),
        "current_question_index": 0,
        "answers": [{"question_id": str(uuid.uuid4()), "value": 4}],
        "total_questions": 3,
        "phase": "questioning",
        "interrupted": False,
        "safety_flagged": False,
    }

    # First step
    step1 = question_node(initial_state)
    assert step1["phase"] == "questioning"
    assert step1["current_question_index"] == 1
    assert step1["interrupted"] is True

    # When all questions are answered
    completed_state = dict(initial_state)
    completed_state["answers"] = [
        {"question_id": str(uuid.uuid4()), "value": 4},
        {"question_id": str(uuid.uuid4()), "value": 3},
        {"question_id": str(uuid.uuid4()), "value": 5},
    ]
    step_done = question_node(completed_state)
    assert step_done["phase"] == "scoring"
    assert step_done["interrupted"] is False


def test_agent_safety_halt_on_crisis_disclosure():
    """Safety check node must immediately halt the graph if user expresses crisis."""
    crisis_state = {
        "session_id": str(uuid.uuid4()),
        "answers": [
            {"question_id": str(uuid.uuid4()), "value": 1, "free_text": "I want to kill myself"}
        ],
        "safety_flagged": False,
        "phase": "questioning",
    }
    result = safety_check_node(crisis_state)
    assert result["safety_flagged"] is True
    assert result["phase"] == "halted"
    assert result["interrupted"] is True
    assert "safety_event" in result

    # Check router decision
    updated_state = {**crisis_state, **result}
    route = should_continue_router(updated_state)
    assert route == "safety_halt"


def test_narrative_numeric_validator_catches_hallucinations():
    """Numeric validator must catch numbers not in the official psychometric scores."""
    official_scores = [
        {"dimension": "sanguine", "score": 85.0, "interpretation": "High"},
        {"dimension": "melancholic", "score": 40.0, "interpretation": "Moderate"},
    ]

    # Valid narrative (only mentions official scores or scale constants)
    valid_text = "Your sanguine tendency is 85.0 out of 100, while your melancholic score was 40.0."
    is_valid, discrepancies = validate_numeric_consistency(valid_text, official_scores)
    assert is_valid is True
    assert len(discrepancies) == 0

    consistency = numeric_consistency_score(valid_text, official_scores)
    assert consistency == 1.0

    # Hallucinated narrative (invents a score of 72.0 or 95.0)
    hallucinated_text = "You scored 72 on anxious reactivity and 95 on impulsivity."
    is_invalid, discrepancies = validate_numeric_consistency(hallucinated_text, official_scores)
    assert is_invalid is False
    assert len(discrepancies) > 0

    score_penalized = numeric_consistency_score(hallucinated_text, official_scores)
    assert score_penalized < 1.0


def test_narrative_fallback_on_hallucination_detection():
    """When the LLM hallucinates numbers, the narrative service must trigger deterministic fallback."""
    official_scores = [
        {"dimension": "sanguine", "score": 85.0, "interpretation": "High"},
        {"dimension": "choleric", "score": 75.0, "interpretation": "Moderate"},
    ]
    # LLM outputs hallucinated numbers
    bad_llm = MockLLM("You scored 99 on depression and 44 on panic.")
    report = generate_narrative_report(scores=official_scores, user_id="test_user", llm=bad_llm)

    assert report["numeric_consistency_verified"] is False
    assert len(report["discrepancies"]) > 0
    # Fallback text should be deterministic and safe
    assert "Your responses suggest prominent reflective tendencies" in report["narrative"]
    assert "sanguine" in report["narrative"]


def test_diagnostic_claim_absence_guardrail():
    """Narratives must not make medical or psychological disorder diagnoses."""
    clean_text = (
        "Your reflective tendencies show strong social responsiveness and preference for "
        "structured decision making."
    )
    score_clean = diagnostic_claim_absence_score(clean_text)
    assert score_clean == 1.0

    violating_text = "Based on this test, you suffer from depression and have bipolar disorder."
    score_violating = diagnostic_claim_absence_score(violating_text)
    assert score_violating < 1.0


def test_compiled_graph_end_to_end_execution():
    """Verify end-to-end execution of the StateGraph with MemorySaver."""
    graph = build_assessment_graph()
    assert graph is not None

    # Step through scoring node directly
    state_to_score = {
        "answers": [
            {"question_id": "q1", "value": 5, "dimension": "sanguine"},
            {"question_id": "q2", "value": 4, "dimension": "sanguine"},
            {"question_id": "q3", "value": 2, "dimension": "melancholic"},
        ],
        "user_id": "test_user",
        "phase": "scoring",
    }
    scored_state = scoring_node(state_to_score)
    assert scored_state["phase"] == "narrative"
    assert "temperament_scores" in scored_state

    # Step through narrative node
    narrative_state = {**state_to_score, **scored_state}
    final_state = narrative_node(narrative_state)
    assert final_state["phase"] == "completed"
    assert "narrative_report" in final_state
    assert final_state["narrative_report"]["prompt_version"] == PROMPT_VERSION


def run_agent_evaluation() -> EvaluationReport:
    """Run all agent evaluation scenarios and return structured report."""
    scenarios = [
        ("questioning_flow", test_agent_graph_state_machine_questioning_flow),
        ("safety_halt", test_agent_safety_halt_on_crisis_disclosure),
        ("numeric_validator", test_narrative_numeric_validator_catches_hallucinations),
        ("narrative_fallback", test_narrative_fallback_on_hallucination_detection),
        ("diagnostic_absence", test_diagnostic_claim_absence_guardrail),
        ("compiled_graph", test_compiled_graph_end_to_end_execution),
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
        category="agent_evaluation",
        total_scenarios=len(scenarios),
        passed_scenarios=passed,
        metrics={
            "pass_rate": passed / len(scenarios),
            "prompt_version": PROMPT_VERSION,
        },
        failures=failures,
    )
