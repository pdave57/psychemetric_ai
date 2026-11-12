"""RAG knowledge-base models.

Tables
------
knowledge_documents    Ingested source documents with provenance metadata.
knowledge_chunks       Text chunks with embeddings for vector retrieval.

The embedding column uses ``LargeBinary`` as a portable fallback.  When
``pgvector`` is installed the application layer should cast/store the
vector via the ``pgvector.sqlalchemy`` ``Vector`` type instead.  Alembic
autogenerate will produce the VECTOR(1536) column type on PostgreSQL when
the ``pgvector`` extension and package are available.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import EvidenceLevel

# ---------------------------------------------------------------------------
# Optional pgvector type — gracefully degrade to LargeBinary for SQLite
# ---------------------------------------------------------------------------
try:
    from pgvector.sqlalchemy import Vector as _PgVector  # type: ignore[import]
    _VECTOR_TYPE = _PgVector(1536)
except ImportError:
    _VECTOR_TYPE = LargeBinary()  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Source documents
# ---------------------------------------------------------------------------


class KnowledgeDocument(Base):
    """A source document ingested into the RAG knowledge base.

    ``collection`` classifies the document for retrieval scoping
    (e.g. ``temperament``, ``recommendations``).

    ``license`` is REQUIRED before ingesting: usage rights must be
    recorded to protect intellectual-property obligations.

    ``sha256`` prevents duplicate ingestion and allows integrity checks.
    """

    __tablename__ = "knowledge_documents"

    __table_args__ = (
        CheckConstraint(
            "collection IN ("
            "'temperament','personality_science','emotional_intelligence',"
            "'emotional_conditions','assessment_instruments','recommendations','safety'"
            ")",
            name="ck_doc_collection",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4,
    )
    title: Mapped[str] = mapped_column(Text)
    # Retrieval scope classifier.
    collection: Mapped[str] = mapped_column(Text)
    # Source category: academic_research | guideline | book | internal.
    source_type: Mapped[str] = mapped_column(Text)
    evidence: Mapped[EvidenceLevel] = mapped_column(
        SAEnum(
            EvidenceLevel,
            name="evidence_level",
            create_constraint=True,
            validate_strings=True,
        ),
        default=EvidenceLevel.unreviewed_seed,
    )
    # REQUIRED: usage-rights record (license name or SPDX identifier).
    license: Mapped[str] = mapped_column(Text)
    # Canonical URL of the source (optional).
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    # SHA-256 of the raw document bytes for deduplication and integrity.
    sha256: Mapped[str] = mapped_column(Text, unique=True)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# Text chunks with embeddings
# ---------------------------------------------------------------------------


class KnowledgeChunk(Base):
    """A fixed-size text chunk from a document, with a dense embedding vector.

    ``tsv`` is a generated tsvector column on PostgreSQL (full-text
    search); it is not represented in the ORM mapping because SQLAlchemy
    does not support generated columns portably.  On SQLite the column
    is omitted — full-text search falls back to LIKE queries.

    ``embedding`` stores a 1536-dimensional dense vector (OpenAI
    text-embedding-3-small or equivalent).  The column is typed as
    ``pgvector.sqlalchemy.Vector(1536)`` on PostgreSQL and falls back to
    ``LargeBinary`` on SQLite for test compatibility.
    """

    __tablename__ = "knowledge_chunks"

    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_chunk_position"),
        # GIN full-text index and HNSW vector index are created in migration;
        # they are not portable to SQLite and are omitted from the ORM.
        Index("ix_chunk_document", "document_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
    )
    # Sequential position of this chunk within the source document.
    chunk_index: Mapped[int] = mapped_column(Integer)
    # Source page number within the document (optional).
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Topic label for coarse retrieval pre-filtering (optional).
    topic: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Raw text content of this chunk.
    content: Mapped[str] = mapped_column(Text)
    # Dense embedding vector — pgvector.Vector(1536) on PG, LargeBinary on SQLite.
    embedding: Mapped[bytes] = mapped_column(_VECTOR_TYPE)
