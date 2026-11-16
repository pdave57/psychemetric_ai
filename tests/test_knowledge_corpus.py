"""Tests for Knowledge Corpus extraction, concept chunking, licensing gate, and retrieval."""

import pytest
from app.knowledge.chunking import clean_text, chunk_by_concepts, EXCLUSION_KEYWORDS
from app.knowledge.corpus_loader import CORPUS_MANIFEST, load_corpus_documents
from app.knowledge.ingestion import ingest_corpus_manifest, LicenseMissingError
from app.knowledge.retrieval import search_knowledge_base


def test_clean_text_normalizes_and_removes_noise():
    raw = "Access for free at https://openstax.org \n\n Chapter 1 Overview \n  Extra   spaces. "
    cleaned = clean_text(raw)
    assert "https" not in cleaned
    assert "Access for free" not in cleaned
    assert "Chapter 1 Overview" not in cleaned
    assert cleaned == "Extra spaces."


def test_diagnostic_exclusion_filter():
    """Ensure text mentioning DSM-5 or clinical psychiatric pathology is excluded."""
    diagnostic_text = (
        "In evaluating DSM-5 criteria, patients diagnosed with borderline personality disorder "
        "show marked affective instability and impulsive reactivity."
    )
    chunks = chunk_by_concepts(diagnostic_text, topic="temperament")
    assert len(chunks) == 0


def test_concept_chunking_word_bounds_and_tagging():
    """Verify that chunk_by_concepts attaches correct concept tags and respects target size."""
    sample = " ".join([f"word{i}" for i in range(300)])
    chunks = chunk_by_concepts(
        text=sample,
        target_words=200,
        overlap_words=30,
        topic="temperament",
        subscale="sanguine",
        concept="sanguine_temperament_profile",
        page=3,
    )
    assert len(chunks) == 2
    assert chunks[0]["topic"] == "temperament"
    assert chunks[0]["subscale"] == "sanguine"
    assert chunks[0]["concept"] == "sanguine_temperament_profile"
    assert chunks[0]["page"] == 3
    assert chunks[0]["word_count"] == 200
    assert chunks[1]["word_count"] > 0


def test_corpus_manifest_licensing_compliance():
    """Every entry in CORPUS_MANIFEST must specify an open-access or Creative Commons license."""
    assert len(CORPUS_MANIFEST) >= 5
    for item in CORPUS_MANIFEST:
        assert "license" in item
        assert item["license"].strip() != ""
        # Disallow raw ingestion of proprietary standards
        assert "AERA" not in item["license"]
        assert any(lic in item["license"] for lic in ["CC BY", "CC-BY", "IGO", "Open-Access"])


def test_corpus_loader_extracts_chunks():
    """Verify the loader extracts real chunks from the PDF documents in knowledge_base/."""
    docs = list(load_corpus_documents())
    assert len(docs) >= 5
    total_chunks = sum(len(d["chunks"]) for d in docs)
    # The 5 corpus documents generate ~188 chunks
    assert total_chunks > 100
    for doc in docs:
        assert doc["license"] != ""
        assert len(doc["chunks"]) > 0
        for ch in doc["chunks"]:
            assert ch["content"] != ""
            assert ch["word_count"] > 0


def test_ingest_corpus_manifest_and_retrieval(db):
    """Test full database ingestion of the corpus and metadata filtering."""
    # 1. Ingest manifest
    res1 = ingest_corpus_manifest(db)
    assert res1["status"] == "success"
    assert res1["documents_added"] >= 5
    assert res1["chunks_added"] > 100

    # 2. Idempotent re-run should not create duplicates
    res2 = ingest_corpus_manifest(db)
    assert res2["documents_added"] == 0
    assert res2["chunks_added"] == 0
    assert all(d["status"] == "existing" for d in res2["documents"])

    # 3. Filtered retrieval by topic
    results_temp = search_knowledge_base(db, query="energy and enthusiasm", topic="temperament")
    assert len(results_temp) > 0
    assert all(r["topic"] == "temperament" for r in results_temp)

    # 4. Filtered retrieval by concept
    results_somatic = search_knowledge_base(
        db, query="grounding breathing", topic="safety", concept="grounding_and_somatic_stabilization"
    )
    assert len(results_somatic) > 0
    assert "safety" in results_somatic[0]["collection"]

    # 5. Filtered retrieval by subscale
    results_sanguine = search_knowledge_base(
        db, query="spontaneous lively social", subscale="sanguine"
    )
    assert len(results_sanguine) > 0
    assert any("sanguine" in r["content"].lower() for r in results_sanguine)


def test_api_corpus_ingest_and_search_endpoints(client, db):
    """Test FastAPI endpoints for corpus ingestion and filtered search."""
    # Call ingest endpoint
    post_res = client.post("/api/v1/knowledge/corpus/ingest")
    assert post_res.status_code == 200
    data = post_res.json()
    assert data["status"] == "success"

    # Search endpoint with topic and concept query params
    search_res = client.get(
        "/api/v1/knowledge/search",
        params={
            "query": "temperament stability",
            "topic": "personality_science",
            "limit": 3,
        },
    )
    assert search_res.status_code == 200
    search_data = search_res.json()
    assert "results" in search_data
    assert len(search_data["results"]) > 0
    assert all(r["topic"] == "personality_science" for r in search_data["results"])
