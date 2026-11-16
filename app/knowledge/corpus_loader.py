"""Corpus loader and PDF extractor for PsychemetreAI / Agent Bleu RAG corpus.

Extracts text from verified open-access and creative commons PDFs in
knowledge_base/ according to the Knowledge Corpus Plan.
"""

from pathlib import Path
from typing import List, Dict, Any, Generator
import pypdf

from app.knowledge.chunking import chunk_by_concepts

KNOWLEDGE_BASE_DIR = Path(__file__).resolve().parents[2] / "knowledge_base"


# Verified Corpus Manifest based on knowledge_corpus_plan.xlsx
CORPUS_MANIFEST = [
    {
        "id": "allen_balance_personality",
        "title": "The Balance of Personality",
        "author": "Chris Allen, Portland State University",
        "file_path": "personality/The Balance of Personality.pdf",
        "license": "CC BY-NC-SA 4.0",
        "collection": "personality_science",
        "evidence": "expert_reviewed",
        "sections": [
            {
                "topic": "personality_science",
                "concept": "five_factor_traits",
                "pages": range(14, 28),  # Ch. 1: Personality Traits
                "subscale": "general",
            },
            {
                "topic": "personality_science",
                "concept": "trait_stability_over_time",
                "pages": range(29, 45),  # Ch. 2: Personality Stability
                "subscale": "general",
            },
            {
                "topic": "assessment_instruments",
                "concept": "personality_assessment_literacy",
                "pages": range(46, 65),  # Ch. 3: Personality Assessment & Reliability
                "subscale": "general",
            },
        ],
    },
    {
        "id": "four_temperaments_guidebook",
        "title": "The Four Temperaments: A Complete Manifesto",
        "author": "Psychemetre / Four Type",
        "file_path": "temperament/four-temperaments-guidebook.pdf",
        "license": "CC-BY-4.0",
        "collection": "temperament",
        "evidence": "expert_reviewed",
        "sections": [
            {
                "topic": "temperament",
                "concept": "classical_temperament_foundations",
                "pages": range(1, 3),
                "subscale": "general",
            },
            {
                "topic": "temperament",
                "concept": "sanguine_temperament_profile",
                "pages": range(2, 4),
                "subscale": "sanguine",
            },
            {
                "topic": "temperament",
                "concept": "choleric_temperament_profile",
                "pages": range(3, 5),
                "subscale": "choleric",
            },
            {
                "topic": "temperament",
                "concept": "melancholic_temperament_profile",
                "pages": range(4, 6),
                "subscale": "melancholic",
            },
            {
                "topic": "temperament",
                "concept": "phlegmatic_temperament_profile",
                "pages": range(5, 7),
                "subscale": "phlegmatic",
            },
        ],
    },
    {
        "id": "temps_a_validation",
        "title": "TEMPS-A Validation and Affective Temperament Dimensions",
        "author": "Jovici et al. / Psychiatria Danubina (Akiskal framework)",
        "file_path": "personality/TEMPS-A.pdf",
        "license": "CC BY 4.0",
        "collection": "temperament",
        "evidence": "research_supported",
        "sections": [
            {
                "topic": "temperament",
                "concept": "temps_affective_temperament_subscales",
                "pages": range(0, 8),
                "subscale": "general",
            },
        ],
    },
    {
        "id": "cloninger_temperament_genetics",
        "title": "The Complex Genetics and Biology of Human Temperament",
        "author": "C. Robert Cloninger et al. (Translational Psychiatry)",
        "file_path": "temperament/The complex genetics and biology of human.pdf",
        "license": "CC BY 4.0",
        "collection": "temperament",
        "evidence": "research_supported",
        "sections": [
            {
                "topic": "temperament",
                "concept": "biological_and_evolutionary_temperament",
                "pages": range(0, 7),
                "subscale": "general",
            },
        ],
    },
    {
        "id": "who_doing_what_matters",
        "title": "Doing What Matters in Times of Stress: An Illustrated Guide",
        "author": "World Health Organization (WHO)",
        "file_path": "personality/Doing-What-Matters.pdf",
        "license": "CC BY-NC-SA 3.0 IGO",
        "collection": "safety",
        "evidence": "clinical_guideline",
        "sections": [
            {
                "topic": "safety",
                "concept": "grounding_and_somatic_stabilization",
                "pages": range(6, 35),
                "subscale": "general",
            },
            {
                "topic": "safety",
                "concept": "unhooking_from_difficult_thoughts",
                "pages": range(36, 65),
                "subscale": "general",
            },
            {
                "topic": "safety",
                "concept": "acting_on_values_and_being_kind",
                "pages": range(66, 105),
                "subscale": "general",
            },
        ],
    },
]


def extract_pdf_section_text(pdf_path: Path, page_range: range) -> str:
    """Extract and concatenate text from a specified page range in a PDF."""
    if not pdf_path.exists():
        return ""

    try:
        reader = pypdf.PdfReader(str(pdf_path))
        num_pages = len(reader.pages)
        extracted = []

        for p_idx in page_range:
            if 0 <= p_idx < num_pages:
                text = reader.pages[p_idx].extract_text()
                if text:
                    extracted.append(text)

        return "\n\n".join(extracted)
    except Exception as e:
        print(f"Error extracting {pdf_path}: {e}")
        return ""


def load_corpus_documents() -> Generator[Dict[str, Any], None, None]:
    """Iterate through the corpus manifest, extract designated PDF sections, and chunk them."""
    for item in CORPUS_MANIFEST:
        pdf_file = KNOWLEDGE_BASE_DIR / item["file_path"]
        if not pdf_file.exists():
            continue

        doc_chunks = []
        for sec in item["sections"]:
            sec_text = extract_pdf_section_text(pdf_file, sec["pages"])
            if not sec_text:
                continue

            chunks = chunk_by_concepts(
                text=sec_text,
                target_words=220,
                overlap_words=35,
                topic=sec["topic"],
                subscale=sec["subscale"],
                concept=sec["concept"],
                page=list(sec["pages"])[0] + 1 if list(sec["pages"]) else None,
            )
            doc_chunks.extend(chunks)

        if doc_chunks:
            yield {
                "manifest_id": item["id"],
                "title": item["title"],
                "author": item["author"],
                "license": item["license"],
                "collection": item["collection"],
                "evidence": item["evidence"],
                "chunks": doc_chunks,
            }
