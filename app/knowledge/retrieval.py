"""Hybrid and semantic retrieval engine across ingested knowledge chunks."""

import math
from typing import List, Dict, Any, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.knowledge import KnowledgeChunk, KnowledgeDocument
from app.knowledge.embeddings import generate_embedding


def _cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    if not vec1 or not vec2:
        return 0.0
    dot = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = math.sqrt(sum(a * a for a in vec1)) or 1.0
    norm2 = math.sqrt(sum(b * b for b in vec2)) or 1.0
    return dot / (norm1 * norm2)


def search_knowledge_base(
    db: Session,
    query: str,
    collection: Optional[str] = None,
    limit: int = 5
) -> List[Dict[str, Any]]:
    """Hybrid search combining keyword frequency and vector similarity."""
    query_vec = generate_embedding(query)
    query_words = set(query.lower().split())

    stmt = select(KnowledgeChunk, KnowledgeDocument).join(
        KnowledgeDocument, KnowledgeChunk.document_id == KnowledgeDocument.id
    )
    if collection:
        stmt = stmt.where(KnowledgeDocument.collection == collection)

    rows = db.execute(stmt).all()
    results = []

    for chunk, doc in rows:
        chunk_words = set(chunk.content.lower().split())
        keyword_overlap = len(query_words.intersection(chunk_words)) / max(len(query_words), 1)

        chunk_emb = chunk.embedding
        if isinstance(chunk_emb, list):
            vec_sim = _cosine_similarity(query_vec, chunk_emb)
        else:
            vec_sim = 0.5

        # Evidence weighting boost
        evidence_weight = {
            "clinical_guideline": 1.3,
            "research_supported": 1.2,
            "expert_reviewed": 1.1,
            "unreviewed_seed": 1.0,
        }.get(doc.evidence.value if hasattr(doc.evidence, "value") else str(doc.evidence), 1.0)

        # Reciprocal rank / hybrid score
        hybrid_score = (0.6 * vec_sim + 0.4 * keyword_overlap) * evidence_weight

        results.append({
            "chunk_id": chunk.id,
            "document_id": doc.id,
            "title": doc.title,
            "collection": doc.collection,
            "license": doc.license,
            "evidence": doc.evidence.value if hasattr(doc.evidence, "value") else str(doc.evidence),
            "content": chunk.content,
            "score": round(hybrid_score, 4),
        })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:limit]
