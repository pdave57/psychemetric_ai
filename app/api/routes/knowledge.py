"""Knowledge base API routes: document ingestion, license check, and hybrid retrieval."""

from typing import Optional, Literal
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db, run_sync
from app.knowledge.ingestion import ingest_document, ingest_corpus_manifest, LicenseMissingError
from app.knowledge.retrieval import search_knowledge_base
from app.models.enums import EvidenceLevel

router = APIRouter()


class IngestionRequest(BaseModel):
    title: str
    collection: Literal[
        "temperament", "personality_science", "emotional_intelligence",
        "emotional_conditions", "assessment_instruments", "recommendations", "safety"
    ]
    source_type: str = "academic_research"
    license: str = Field(..., description="Mandatory license identifier, e.g. 'CC-BY-4.0', 'Open-Access'")
    content: str = Field(..., min_length=20)
    evidence: Optional[EvidenceLevel] = EvidenceLevel.unreviewed_seed
    source_url: Optional[str] = None
    topic: Optional[str] = None


@router.post("/ingest", status_code=status.HTTP_201_CREATED)
async def ingest_text_document(payload: IngestionRequest, db: Session = Depends(get_db)):
    """Ingest research document text with license gating and chunking."""
    try:
        doc = await run_sync(
            ingest_document,
            db=db,
            title=payload.title,
            collection=payload.collection,
            source_type=payload.source_type,
            license=payload.license,
            content=payload.content,
            evidence=payload.evidence or EvidenceLevel.unreviewed_seed,
            source_url=payload.source_url,
            topic=payload.topic,
        )
        return {
            "document_id": doc.id,
            "title": doc.title,
            "sha256": doc.sha256,
            "collection": doc.collection,
            "license": doc.license,
            "status": "ingested",
        }
    except LicenseMissingError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/corpus/ingest", status_code=status.HTTP_200_OK)
async def trigger_corpus_ingestion(
    force_reload: bool = False,
    db: Session = Depends(get_db)
):
    """Trigger ingestion of verified corpus manifest documents into knowledge base."""
    try:
        return await run_sync(ingest_corpus_manifest, db=db, force_reload=force_reload)
    except LicenseMissingError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/search")
async def search_knowledge(
    query: str,
    collection: Optional[str] = None,
    topic: Optional[str] = None,
    subscale: Optional[str] = None,
    concept: Optional[str] = None,
    limit: int = 5,
    db: Session = Depends(get_db)
):
    """Retrieve supporting research citations and chunks for a query."""
    if not query.strip():
        return {"query": query, "results": []}
    results = await run_sync(
        search_knowledge_base,
        db,
        query=query,
        collection=collection,
        topic=topic,
        subscale=subscale,
        concept=concept,
        limit=limit,
    )
    return {"query": query, "count": len(results), "results": results}
