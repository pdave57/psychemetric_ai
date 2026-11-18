"""LangGraph assessment orchestration workflow with checkpointing, interrupt, and safety halt."""

from typing import Dict, Any, Literal
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from app.agents.state import AssessmentGraphState
from app.agents.safety_agent import safety_agent_node
from app.agents.planner import planner_node, route_from_planner
from app.agents.question_agent import question_agent_node
from app.agents.response_agent import response_agent_node
from app.agents.report_agent import (
    report_agent_scoring_node,
    report_agent_narrative_node,
    report_agent_node,
)

# Backwards-compatible aliases
safety_check_node = safety_agent_node
question_node = question_agent_node
scoring_node = report_agent_scoring_node
narrative_node = report_agent_narrative_node
should_continue_router = route_from_planner


def build_assessment_graph(checkpointer=None):
    """Build and compile the modular LangGraph assessment workflow."""
    checkpointer = checkpointer or MemorySaver()

    builder = StateGraph(AssessmentGraphState)

    builder.add_node("safety_check", safety_agent_node)
    builder.add_node("question_node", question_agent_node)
    builder.add_node("scoring_node", report_agent_scoring_node)
    builder.add_node("narrative_node", report_agent_narrative_node)

    # Halt node
    def safety_halt_node(state: AssessmentGraphState) -> Dict[str, Any]:
        return {"phase": "halted"}
    builder.add_node("safety_halt", safety_halt_node)

    # Edges
    builder.add_edge(START, "safety_check")

    builder.add_conditional_edges(
        "safety_check",
        route_from_planner,
        {
            "safety_halt": "safety_halt",
            "question_node": "question_node",
            "scoring_node": "scoring_node",
            "narrative_node": "narrative_node",
        }
    )

    builder.add_edge("question_node", END)
    builder.add_edge("scoring_node", "narrative_node")
    builder.add_edge("narrative_node", END)
    builder.add_edge("safety_halt", END)

    return builder.compile(checkpointer=checkpointer)
