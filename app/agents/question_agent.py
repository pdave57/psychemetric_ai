"""Question delivery, sequencing, and presentation agent.

Manages psychometric item sequencing, guards against unauthorized question
modifications or diagnostic framing, and packages items with standard
5-point Likert response options for frontend rendering.
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from app.agents.state import AssessmentGraphState

_KNOWLEDGE_PACK_DIR = Path(__file__).resolve().parents[1] / "knowledge_pack"
_TEMPERAMENT_FILE = _KNOWLEDGE_PACK_DIR / "temperament_bank.json"

_DEFAULT_OPTIONS = [
    {"code": "1", "text": "Strongly disagree"},
    {"code": "2", "text": "Disagree"},
    {"code": "3", "text": "Neutral"},
    {"code": "4", "text": "Agree"},
    {"code": "5", "text": "Strongly agree"},
]


def load_canonical_questions() -> List[Dict[str, Any]]:
    """Load canonical 40-item temperament questions from the knowledge pack."""
    if _TEMPERAMENT_FILE.exists():
        try:
            with open(_TEMPERAMENT_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("questions", [])
        except Exception:
            pass
    return []


def validate_question_format(q: Dict[str, Any]) -> bool:
    """Ensure question complies with length caps, non-diagnostic tone, and options."""
    text = q.get("text", "")
    if not text or len(text) < 5 or len(text) > 300:
        return False
    # Avoid clinical diagnostic language
    lower = text.lower()
    if any(w in lower for w in ["dsm", "disorder", "diagnosis", "pathology"]):
        return False
    return True


def get_next_question(state: AssessmentGraphState) -> Optional[Dict[str, Any]]:
    """Determine the next question dict to present."""
    answers = state.get("answers", [])
    idx = len(answers)
    total = state.get("total_questions", 16)

    if idx >= total:
        return None

    # 1. Use state-provided questions list if populated
    state_qs = state.get("questions")
    if state_qs and idx < len(state_qs):
        q = state_qs[idx]
        return {
            "id": str(q.get("id", f"q_{idx+1}")),
            "code": q.get("code", f"Q{idx+1:02d}"),
            "text": q.get("text", ""),
            "dimension": q.get("dimension", "sanguine"),
            "reverse_coded": q.get("reverse_coded", False),
            "options": q.get("options", _DEFAULT_OPTIONS),
            "index": idx,
            "total": total,
        }

    # 2. Fallback to canonical bank
    canonical = load_canonical_questions()
    if canonical and idx < len(canonical):
        cq = canonical[idx]
        return {
            "id": cq.get("code", f"q_{idx+1}"),
            "code": cq.get("code", f"Q{idx+1:02d}"),
            "text": cq.get("text", ""),
            "dimension": cq.get("dimension", "sanguine"),
            "reverse_coded": cq.get("reverse_coded", False),
            "options": _DEFAULT_OPTIONS,
            "index": idx,
            "total": total,
        }

    # 3. Default fallback item
    return {
        "id": f"q_{idx+1}",
        "code": f"Q{idx+1:02d}",
        "text": "I feel energised when engaging in focused projects.",
        "dimension": "sanguine",
        "reverse_coded": False,
        "options": _DEFAULT_OPTIONS,
        "index": idx,
        "total": total,
    }


def question_agent_node(state: AssessmentGraphState) -> Dict[str, Any]:
    """Question delivery node for LangGraph orchestration.

    If all questions have been answered:
      transitions phase to `"scoring"` with `interrupted = False`.
    Otherwise:
      selects the next question, sets `pending_question`, and pauses (`interrupted = True`).
    """
    answers = state.get("answers", [])
    total = state.get("total_questions", 16)
    idx = len(answers)

    if idx >= total:
        return {
            "phase": "scoring",
            "interrupted": False,
        }

    next_q = get_next_question(state)

    return {
        "current_question_index": idx,
        "pending_question": next_q,
        "phase": "questioning",
        "interrupted": True,  # Interrupted so client/user can answer
    }
