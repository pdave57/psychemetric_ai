"""Lightweight, self-contained PDF generator for assessment reports.

Outputs clean PDF 1.4 documents containing report headers, disclaimers,
quantitative scores, and recommendations.
"""

import io
from typing import Dict, Any, List


def generate_assessment_pdf(report_data: Dict[str, Any]) -> bytes:
    """Generate a clean PDF report without external binary dependencies."""
    output = io.BytesIO()

    # Build PDF content stream
    session_id = report_data.get("session_id", "Unknown")
    scores = report_data.get("temperament_scores", [])
    disclaimer = report_data.get(
        "disclaimer",
        "Reflective framework only; not a clinical psychological or diagnostic evaluation."
    )
    narrative = report_data.get("narrative", "")

    # PDF header & objects
    lines = [
        "%PDF-1.4",
        "1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj",
        "2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj",
        "3 0 obj << /Type /Page /Parent 2 0 R /Resources << /Font << /F1 4 0 R >> >> /MediaBox [0 0 612 792] /Contents 5 0 R >> endobj",
        "4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj",
    ]

    # Format text for the content stream
    content_commands = [
        "BT",
        "/F1 18 Tf",
        "50 740 Td",
        "(PsychemetreAI - Personal Assessment Report) Tj",
        "/F1 10 Tf",
        "0 -25 Td",
        f"(Session ID: {session_id}) Tj",
        "0 -20 Td",
        "(---------------------------------------------------------------------------------------------------) Tj",
        "0 -25 Td",
        "/F1 12 Tf",
        "(Temperament Scores:) Tj",
        "/F1 10 Tf",
    ]

    for s in scores:
        dim = s.get("dimension", "")
        score_val = s.get("normalized_score") or s.get("score") or 0.0
        interp = s.get("interpretation", "")
        content_commands.extend([
            "0 -18 Td",
            f"(  * {dim.capitalize()}: {score_val}/100 - {interp[:60]}) Tj"
        ])

    if narrative:
        content_commands.extend([
            "0 -25 Td",
            "/F1 12 Tf",
            "(Reflective Narrative:) Tj",
            "/F1 10 Tf",
            "0 -18 Td",
            f"({narrative[:85]}...) Tj",
        ])

    content_commands.extend([
        "0 -35 Td",
        "/F1 9 Tf",
        "(IMPORTANT DISCLAIMER:) Tj",
        "0 -14 Td",
        f"({disclaimer[:90]}) Tj",
        "ET"
    ])

    stream_content = "\n".join(content_commands).encode("latin-1")
    stream_len = len(stream_content)

    obj5 = f"5 0 obj << /Length {stream_len} >>\nstream\n".encode("latin-1") + stream_content + b"\nendstream\nendobj"

    pdf_body = "\n".join(lines).encode("latin-1") + b"\n" + obj5 + b"\nxref\n0 6\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n0000000244 00000 n \n0000000318 00000 n \ntrailer << /Size 6 /Root 1 0 R >>\nstartxref\n500\n%%EOF"

    output.write(pdf_body)
    return output.getvalue()
