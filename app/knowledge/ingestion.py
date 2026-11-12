"""Knowledge ingestion pipeline with strict licensing gate and deduplication."""

import hashlib
import uuid
from typing import List, Dict, Any, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.knowledge import KnowledgeDocument, KnowledgeChunk
from app.models.enums import EvidenceLevel
from app.knowledge.chunking import chunk_text
from app.knowledge.embeddings import generate_embedding


class LicenseMissingError(ValueError):
    """Raised when an ingestion attempt lacks mandatory license metadata."""
    pass


def ingest_document(
    db: Session,
    title: str,
    collection: str,
    source_type: str,
    license: str,
    content: str,
    evidence: EvidenceLevel = EvidenceLevel.unreviewed_seed,
    source_url: Optional[str] = None,
    topic: Optional[str] = None,
) -> KnowledgeDocument:
    """Ingest a source text document into knowledge_documents and knowledge_chunks.

    Enforces:
      1. Mandatory license check.
      2. SHA-256 deduplication (idempotent; returns existing if hash matches).
    """
    if not license or not license.strip():
        raise LicenseMissingError("Mandatory 'license' field is required before ingesting research material.")

    sha256_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

    existing = db.scalar(
        select(KnowledgeDocument).where(KnowledgeDocument.sha256 == sha256_hash)
    )
    if existing:
        return existing

    doc = KnowledgeDocument(
        title=title,
        collection=collection,
        source_type=source_type,
        license=license.strip(),
        source_url=source_url,
        sha256=sha256_hash,
        evidence=evidence,
    )
    db.add(doc)
    db.flush()

    # Chunk content
    chunks = chunk_text(content, chunk_size=100, overlap=10)
    for c in chunks:
        emb = generate_embedding(c["content"])
        chunk_obj = KnowledgeChunk(
            document_id=doc.id,
            chunk_index=c["chunk_index"],
            topic=topic,
            content=c["content"],
            embedding=emb,
        )
        db.add(chunk_obj)

    db.commit()
    db.refresh(doc)
    return doc
