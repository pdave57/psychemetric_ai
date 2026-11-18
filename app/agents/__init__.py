"""Multi-agent assessment orchestration package.

Contains specialized agents:
- `planner`: Coordinates overall assessment trajectory and transitions.
- `safety_agent`: Continuously screens for crisis / self-harm signals.
- `question_agent`: Delivers psychometric questions with formatting & length guards.
- `response_agent`: Validates responses and extracts qualitative emotion evidence.
- `report_agent`: Computes deterministic scores and synthesizes reflective narratives.
- `state`: Canonical TypedDict schema representing shared assessment state.
- `graph`: LangGraph workflow engine with checkpointing and interrupts.
"""

from app.agents.state import AssessmentGraphState, create_initial_state
from app.agents.planner import planner_node, route_from_planner, create_assessment_plan
from app.agents.safety_agent import safety_agent_node, evaluate_safety
from app.agents.question_agent import question_agent_node, get_next_question, validate_question_format
from app.agents.response_agent import response_agent_node, validate_answer_value, extract_emotion_signals
from app.agents.report_agent import (
    report_agent_scoring_node,
    report_agent_narrative_node,
    report_agent_node,
)
from app.agents.graph import (
    build_assessment_graph,
    safety_check_node,
    question_node,
    scoring_node,
    narrative_node,
    should_continue_router,
)

__all__ = [
    "AssessmentGraphState",
    "create_initial_state",
    "planner_node",
    "route_from_planner",
    "create_assessment_plan",
    "safety_agent_node",
    "evaluate_safety",
    "question_agent_node",
    "get_next_question",
    "validate_question_format",
    "response_agent_node",
    "validate_answer_value",
    "extract_emotion_signals",
    "report_agent_scoring_node",
    "report_agent_narrative_node",
    "report_agent_node",
    "build_assessment_graph",
    "safety_check_node",
    "question_node",
    "scoring_node",
    "narrative_node",
    "should_continue_router",
]
