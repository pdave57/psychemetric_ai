"""Crisis detection, triage, and safety sentinel agent.

Continuously monitors respondent free text, answers, and messages for
self-harm, suicidal ideation, abuse, and acute distress signals.
Halts the workflow immediately when a risk event is detected, attaching
verified 24/7 crisis helplines and preventing clinical diagnostic claims.
"""

from typing import Dict, Any, Optional
from app.agents.state import AssessmentGraphState
from app.core.safety_protocol import screen_text_for_safety, VERIFIED_RESOURCES


def evaluate_safety(text: Optional[str]) -> Optional[Dict[str, Any]]:
    """Screen free text against crisis and emergency intervention protocols."""
    if not text or not text.strip():
        return None
    return screen_text_for_safety(text)


def safety_agent_node(state: AssessmentGraphState) -> Dict[str, Any]:
    """Safety screening node for the LangGraph workflow.

    Checks:
      1. Explicit `last_user_message` if present.
      2. The latest answer's `free_text` or `text` field.

    If safety risk detected:
      - Sets `safety_flagged = True`.
      - Transitions phase to `"halted"`.
      - Attaches emergency helpline resources.
      - Sets `interrupted = True` to halt questionnaire progression.
    """
    candidate_texts = []

    # Check last direct user message
    if state.get("last_user_message"):
        candidate_texts.append(state["last_user_message"])

    # Check latest answer
    answers = state.get("answers", [])
    if answers:
        latest = answers[-1]
        text_val = latest.get("free_text") or latest.get("text")
        if text_val:
            candidate_texts.append(text_val)

    # Screen each candidate text
    for text in candidate_texts:
        risk = evaluate_safety(text)
        if risk:
            return {
                "safety_flagged": True,
                "safety_level": risk.get("level", "critical"),
                "safety_event": risk,
                "safety_message": risk.get("message"),
                "verified_resources": risk.get("resources", VERIFIED_RESOURCES),
                "phase": "halted",
                "interrupted": True,
            }

    return {
        "safety_flagged": False,
        "safety_level": None,
    }
