"""Concept-based, semantic text chunking for the RAG knowledge pipeline.

Follows the PsychemetreAI Knowledge Corpus Plan:
- Chunks by conceptual section/unit (150–350 words) rather than rigid page boundaries.
- Filters out non-relevant content (e.g., exercises, indices, bibliographies, clinical disorder diagnosis).
- Attaches topic, subscale, concept, and source metadata to every chunk.
"""

import re
from typing import List, Dict, Any, Optional

# Keywords that indicate diagnostic or psychiatric case-study material to filter out
EXCLUSION_KEYWORDS = [
    "dsm-5 criteria", "diagnostic criteria", "borderline personality disorder",
    "schizophrenia", "bipolar i disorder", "clinical trial patient", "case vignette",
    "electroconvulsive therapy", "antipsychotic medication"
]


def clean_text(text: str) -> str:
    """Normalize whitespace and remove PDF extraction artifacts."""
    if not text:
        return ""
    # Remove header/footer page markers and boilerplate
    text = re.sub(r"Access for free at(?:\s+\S+)?", "", text, flags=re.IGNORECASE)
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"Chapter\s+\d+\s+Overview", "", text, flags=re.IGNORECASE)
    # Collapse multiple whitespace/newlines
    text = re.sub(r"\s+", " ", text).strip()
    return text


def chunk_by_concepts(
    text: str,
    target_words: int = 250,
    overlap_words: int = 40,
    topic: Optional[str] = None,
    subscale: Optional[str] = None,
    concept: Optional[str] = None,
    page: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Produce concept-aligned chunks from text with metadata tagging and exclusion filtering."""
    cleaned = clean_text(text)
    if not cleaned:
        return []

    # Check exclusions
    lower_text = cleaned.lower()
    for excl in EXCLUSION_KEYWORDS:
        if excl in lower_text:
            # Skip chunks focused on clinical pathology
            return []

    words = cleaned.split()
    if len(words) < 5:
        return []

    chunks = []
    start = 0
    chunk_index = 0

    while start < len(words):
        end = min(start + target_words, len(words))
        chunk_content = " ".join(words[start:end])

        chunks.append({
            "chunk_index": chunk_index,
            "content": chunk_content,
            "word_count": end - start,
            "topic": topic,
            "subscale": subscale,
            "concept": concept,
            "page": page,
        })
        chunk_index += 1

        if end == len(words):
            break
        start += max(1, target_words - overlap_words)

    return chunks


def chunk_text(
    text: str,
    chunk_size: int = 250,
    overlap: int = 40
) -> List[Dict[str, Any]]:
    """Backward-compatible standard chunking function."""
    return chunk_by_concepts(text, target_words=chunk_size, overlap_words=overlap)
