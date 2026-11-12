"""Clinical and safety protocol rules and screening patterns.

Derived from clinician-reviewed crisis intervention protocols and Nigerian
mental health resources (Federal Ministry of Health Crisis Line, SURPIN, etc.).
"""

import json
from pathlib import Path
from typing import Optional, List, Dict, Any

# Standard emergency and support contacts (Nigeria & International fallback)
VERIFIED_RESOURCES = [
    {
        "name": "Nigeria Suicide Prevention Helpline (SURPIN)",
        "contact": "09060001907 / 08062106497",
        "type": "crisis_helpline",
        "hours": "24/7",
        "description": "Suicide Research and Prevention Initiative crisis hotline in Nigeria."
    },
    {
        "name": "Federal Ministry of Health Mental Health Emergency",
        "contact": "0800 021 2121",
        "type": "crisis_helpline",
        "hours": "24/7",
        "description": "National emergency mental health and psychosocial support helpline."
    },
    {
        "name": "She Writes Woman Mental Health Support (Nigeria)",
        "contact": "0708 646 2943",
        "type": "support_line",
        "hours": "Mon-Sat 9am-5pm",
        "description": "Mental health helpline providing tele-counseling and referrals across Nigeria."
    }
]

# Crisis screening pattern indicators
CRITICAL_PATTERNS = [
    "suicide", "kill myself", "end my life", "want to die", "commit suicide",
    "better off dead", "cutting myself", "self harm", "take my own life",
    "hang myself", "overdose", "slit my wrists"
]

HIGH_PATTERNS = [
    "hurt someone", "kill someone", "stab", "physically hurt",
    "abuse", "hopeless", "can't go on", "no reason to live"
]


def screen_text_for_safety(text: Optional[str]) -> Optional[Dict[str, Any]]:
    """Screen free text or responses for crisis/safety signals.

    Returns a dict with safety event attributes if triggered, else None.
    """
    if not text:
        return None

    lower_text = text.lower()

    matched_critical = [p for p in CRITICAL_PATTERNS if p in lower_text]
    if matched_critical:
        return {
            "level": "critical",
            "categories": ["suicide_or_self_harm"],
            "detector": "rules",
            "patterns": matched_critical,
            "resources": VERIFIED_RESOURCES,
            "message": (
                "We noticed you may be in distress. InnerMAP cannot provide emergency care. "
                "Please reach out immediately to one of these free, confidential support services."
            )
        }

    matched_high = [p for p in HIGH_PATTERNS if p in lower_text]
    if matched_high:
        return {
            "level": "high",
            "categories": ["harm_risk_or_crisis"],
            "detector": "rules",
            "patterns": matched_high,
            "resources": VERIFIED_RESOURCES,
            "message": (
                "If you are feeling overwhelmed or unsafe, please consider contacting a trusted "
                "professional or crisis support hotline."
            )
        }

    return None
