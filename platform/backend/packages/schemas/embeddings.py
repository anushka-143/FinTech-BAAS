"""Knowledge chunks schema — vector embeddings for RAG retrieval.

Stores chunked documents with pgvector embeddings for semantic search.
Sources: regulations, investigations, policies, API docs, sanctions context.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from packages.db.base import Base, TenantMixin, TimestampMixin

try:
    from pgvector.sqlalchemy import Vector
    HAS_PGVECTOR = True
except ImportError:
    HAS_PGVECTOR = False


class KnowledgeChunk(Base, TimestampMixin):
    """A chunk of knowledge with its vector embedding.

    tenant_id NULL = global (regulations, sanctions lists).
    tenant_id set = tenant-specific (policies, past investigations).
    """
    __tablename__ = "knowledge_chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=True, index=True)

    # Source tracking
    source_type = Column(
        String(50), nullable=False, index=True,
        comment="regulation | investigation | policy | api_doc | sanctions | runbook",
    )
    source_ref = Column(
        String(500), nullable=False,
        comment="e.g. RBI/2024-25/89, UAPA Schedule 1, case KYC-00123",
    )
    title = Column(String(500), nullable=False)
    content = Column(Text, nullable=False)

    # Vector embedding (768-dim from gemini-embedding-001 via MRL)
    if HAS_PGVECTOR:
        embedding = Column(Vector(768), nullable=True)
    else:
        # Fallback for environments without pgvector installed
        embedding = Column(Text, nullable=True, comment="JSON array of 768 floats")

    # Rich metadata for filtering
    metadata_ = Column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb"),
        comment="section, effective_date, jurisdiction, language, etc.",
    )

    # Chunk position in source document
    chunk_index = Column(String(20), nullable=True, comment="e.g. 3/12")


# IVFFlat index for fast approximate nearest neighbor search
if HAS_PGVECTOR:
    _ivfflat_idx = Index(
        "idx_knowledge_chunks_embedding",
        KnowledgeChunk.embedding,
        postgresql_using="ivfflat",
        postgresql_with={"lists": 100},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )


class EmbeddingLog(Base, TimestampMixin):
    """Tracks embedding generation for cost accounting and audit."""
    __tablename__ = "embedding_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model = Column(String(100), nullable=False, default="gemini-embedding-001")
    input_tokens = Column(String(20), nullable=True)
    chunks_embedded = Column(String(20), nullable=False)
    source_type = Column(String(50), nullable=True)
    tenant_id = Column(UUID(as_uuid=True), nullable=True)
