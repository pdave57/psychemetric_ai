"""Unit and integration tests for modular assessment agents:

- state: canonical TypedDict and factory function
- planner: roadmap generation and transition routing
- safety_agent: continuous crisis screening and intervention
- question_agent: item formatting, options presentation, and progress bounds
- response_agent: Likert validation and emotion signal extraction
- report_agent: deterministic scoring and narrative synthesis
"""

import uuid
import pytest

from app.agents.state import create_initial_state, AssessmentGraphState
from app.agents.planner import planner_node, route_from_planner, create_assessment_plan
from app.agents.safety_agent import safety_agent_node, evaluate_safety
from app.agents.question_agent import question_agent_node, get_next_question, validate_question_format
from app.agents.response_agent import response_agent_node, validate_answer_value, extract_emotion_signals
from app.agents.report_agent import (
    report_agent_scoring_node,
    report_agent_narrative_node,
    report_agent_node,
)
from app.agents.graph import build_assessment_graph


def test_initial_state_factory():
    """Verify create_initial_state initializes all state fields with defaults."""
    state = create_initial_state(session_id="test_sess_1", total_questions=20)
    assert state["session_id"] == "test_sess_1"
    assert state["total_questions"] == 20
    assert state["phase"] == "questioning"
    assert state["answers"] == []
    assert state["safety_flagged"] is False
    assert state["plan"]["current_stage"] == "questioning"


def test_planner_progression_and_routing():
    """Verify planner node monitors progress and routes transitions."""
    plan = create_assessment_plan(total_questions=4)
    state = create_initial_state(session_id="sess_plan", total_questions=4)

    # 1. Incomplete questioning stage
    state["answers"] = [{"question_id": "q1", "value": 4}]
    step1 = planner_node(state)
    assert step1["phase"] == "questioning"
    assert step1["interrupted"] is True
    assert route_from_planner(step1) == "question_node"

    # 2. Reached total questions threshold
    state["answers"] = [
        {"question_id": "q1", "value": 4},
        {"question_id": "q2", "value": 3},
        {"question_id": "q3", "value": 5},
        {"question_id": "q4", "value": 2},
    ]
    step2 = planner_node(state)
    assert step2["phase"] == "scoring"
    assert step2["interrupted"] is False
    assert route_from_planner(step2) == "scoring_node"

    # 3. Route to safety halt if safety is flagged
    state["safety_flagged"] = True
    assert route_from_planner(state) == "safety_halt"


def test_safety_agent_detection_and_intervention():
    """Safety agent must intercept crisis signals in answers or messages."""
    # Benign response
    clean_state: AssessmentGraphState = {
        "answers": [{"question_id": "q1", "value": 4, "free_text": "I enjoy sunny walks"}],
        "safety_flagged": False,
    }
    res_clean = safety_agent_node(clean_state)
    assert res_clean["safety_flagged"] is False

    # Crisis in answer free_text
    crisis_state: AssessmentGraphState = {
        "answers": [{"question_id": "q1", "value": 1, "free_text": "I want to end my life"}],
        "safety_flagged": False,
    }
    res_crisis = safety_agent_node(crisis_state)
    assert res_crisis["safety_flagged"] is True
    assert res_crisis["phase"] == "halted"
    assert res_crisis["interrupted"] is True
    assert len(res_crisis["verified_resources"]) >= 2

    # Crisis in last direct user message
    msg_state: AssessmentGraphState = {
        "last_user_message": "I am thinking about suicide",
        "answers": [],
        "safety_flagged": False,
    }
    res_msg = safety_agent_node(msg_state)
    assert res_msg["safety_flagged"] is True
    assert res_msg["safety_level"] == "critical"


def test_question_agent_presentation():
    """Question agent must package items with options and respect completion bounds."""
    state = create_initial_state(session_id="sess_q", total_questions=2)

    # Question 1
    step1 = question_agent_node(state)
    assert step1["phase"] == "questioning"
    assert step1["current_question_index"] == 0
    assert step1["interrupted"] is True
    assert "pending_question" in step1
    q1 = step1["pending_question"]
    assert len(q1["options"]) == 5
    assert validate_question_format(q1) is True

    # After answering all questions
    state["answers"] = [
        {"question_id": "q1", "value": 3},
        {"question_id": "q2", "value": 4},
    ]
    step_done = question_agent_node(state)
    assert step_done["phase"] == "scoring"
    assert step_done["interrupted"] is False


def test_response_agent_validation_and_emotion_extraction():
    """Response agent must validate Likert values and extract qualitative emotion cues."""
    # Value validator
    assert validate_answer_value(4) == 4
    assert validate_answer_value("5") == 5
    assert validate_answer_value(0) is None
    assert validate_answer_value(6) is None

    # Emotion signal extraction
    signals = extract_emotion_signals("I felt very anxious and stressed about my recent exams.")
    emotions = [s["emotion"] for s in signals]
    assert "anxiety" in emotions
    assert "stress" in emotions

    # Response agent node execution
    state = create_initial_state(session_id="sess_resp")
    state["answers"] = [{"question_id": "q1", "value": "4", "free_text": "I felt very calm and happy"}]
    res = response_agent_node(state)
    assert res["answers"][0]["value"] == 4
    assert res["answers"][0]["validated"] is True
    extracted = [e["emotion"] for e in res["extracted_emotions"]]
    assert "calm" in extracted
    assert "joy" in extracted


def test_report_agent_scoring_and_synthesis():
    """Report agent must calculate normalized scores and invoke narrative synthesis."""
    state = create_initial_state(session_id="sess_rep")
    state["answers"] = [
        {"question_id": "q1", "value": 5, "dimension": "sanguine"},
        {"question_id": "q2", "value": 4, "dimension": "sanguine"},
        {"question_id": "q3", "value": 2, "dimension": "melancholic"},
        {"question_id": "q4", "value": 3, "dimension": "choleric"},
    ]

    # Scoring node
    score_res = report_agent_scoring_node(state)
    assert score_res["phase"] == "narrative"
    assert "temperament_scores" in score_res
    dims = score_res["temperament_scores"]["dimensions"]
    assert len(dims) >= 3
    assert score_res["leading_tendencies"][0] == "sanguine"

    # Narrative node
    merged = {**state, **score_res}
    narr_res = report_agent_narrative_node(merged)
    assert narr_res["phase"] == "completed"
    assert "narrative_report" in narr_res
    assert narr_res["narrative_report"]["numeric_consistency_verified"] is True

    # Combined report agent node
    combined = report_agent_node(state)
    assert combined["phase"] == "completed"
    assert "temperament_scores" in combined
    assert "narrative_report" in combined


def test_compiled_graph_integration_with_modular_agents():
    """Verify that build_assessment_graph executes end-to-end with the modular agents."""
    graph = build_assessment_graph()
    assert graph is not None

    # Step through graph via invoke
    thread_config = {"configurable": {"thread_id": str(uuid.uuid4())}}
    init_state = create_initial_state(session_id="integration_sess", total_questions=2)
    init_state["answers"] = [
        {"question_id": "q1", "value": 5, "dimension": "sanguine"},
        {"question_id": "q2", "value": 4, "dimension": "sanguine"},
    ]

    result = graph.invoke(init_state, config=thread_config)
    assert result["phase"] in ("scoring", "completed")
    assert result["safety_flagged"] is False
