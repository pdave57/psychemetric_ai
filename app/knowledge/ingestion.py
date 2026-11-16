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


def ingest_corpus_manifest(db: Session, force_reload: bool = False) -> Dict[str, Any]:
    """Ingest documents and concept chunks from the verified corpus manifest into the database.

    Enforces:
      1. License check on every manifest entry.
      2. Deduplication based on SHA-256 of document content.
      3. Tagging with topic, subscale, and concept metadata.
    """
    from app.knowledge.corpus_loader import load_corpus_documents

    results = {
        "status": "success",
        "documents_processed": 0,
        "documents_added": 0,
        "chunks_added": 0,
        "documents": [],
    }

    for doc_item in load_corpus_documents():
        results["documents_processed"] += 1
        manifest_id = doc_item["manifest_id"]
        license_str = doc_item.get("license", "").strip()

        if not license_str:
            raise LicenseMissingError(f"Corpus document '{doc_item['title']}' is missing a license.")

        # Aggregate content to form a reliable document hash
        combined_text = "\n".join(c["content"] for c in doc_item["chunks"])
        doc_sha = hashlib.sha256((manifest_id + ":" + combined_text).encode("utf-8")).hexdigest()

        existing = db.scalar(
            select(KnowledgeDocument).where(KnowledgeDocument.sha256 == doc_sha)
        )
        if existing and not force_reload:
            results["documents"].append({
                "manifest_id": manifest_id,
                "title": doc_item["title"],
                "status": "existing",
                "document_id": str(existing.id),
                "chunks_count": len(doc_item["chunks"]),
            })
            continue

        if existing and force_reload:
            db.delete(existing)
            db.flush()

        evidence_str = doc_item.get("evidence", "research_supported")
        try:
            evidence_enum = EvidenceLevel(evidence_str)
        except Exception:
            evidence_enum = EvidenceLevel.research_supported

        doc = KnowledgeDocument(
            title=doc_item["title"],
            collection=doc_item["collection"],
            source_type="academic_research",
            license=license_str,
            source_url=f"corpus://{manifest_id}",
            sha256=doc_sha,
            evidence=evidence_enum,
        )
        db.add(doc)
        db.flush()

        chunk_counter = 0
        for idx, c in enumerate(doc_item["chunks"]):
            tagged_content = (
                f"[Topic: {c.get('topic')} | Subscale: {c.get('subscale')} | Concept: {c.get('concept')}]\n"
                f"{c['content']}"
            )
            emb = generate_embedding(tagged_content)
            chunk_obj = KnowledgeChunk(
                document_id=doc.id,
                chunk_index=idx,
                page=c.get("page"),
                topic=c.get("topic"),
                content=tagged_content,
                embedding=emb,
            )
            db.add(chunk_obj)
            chunk_counter += 1

        db.commit()
        db.refresh(doc)
        results["documents_added"] += 1
        results["chunks_added"] += chunk_counter
        results["documents"].append({
            "manifest_id": manifest_id,
            "title": doc.title,
            "status": "created",
            "document_id": str(doc.id),
            "chunks_count": chunk_counter,
        })

    return results


if __name__ == "__main__":
    from app.core.database import SessionLocal
    with SessionLocal() as session:
        output = ingest_corpus_manifest(session)
        print(output)
