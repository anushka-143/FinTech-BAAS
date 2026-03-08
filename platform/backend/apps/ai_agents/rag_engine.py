"""RAG Retrieval Engine — hybrid vector + keyword search over knowledge base.

Pipeline:
  1. Embed query via gemini-embedding-001 (RETRIEVAL_QUERY task type)
  2. pgvector cosine similarity search (top 20 candidates)
  3. Metadata filter (source_type, jurisdiction, tenant scope)
  4. Return top-K with citations and relevance scores
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select, text, func, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.engine import get_session_factory


@dataclass(frozen=True)
class ChunkResult:
    """A retrieved knowledge chunk with relevance metadata."""
    chunk_id: str
    title: str
    content: str
    source_type: str
    source_ref: str
    relevance_score: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RetrievalResult:
    """Complete RAG retrieval output."""
    query: str
    chunks: list[ChunkResult]
    total_candidates: int
    retrieval_method: str  # "vector" | "keyword" | "hybrid"


class RAGEngine:
    """Hybrid retrieval engine over the knowledge_chunks table.

    Supports:
      - Pure vector search (semantic similarity)
      - Pure keyword search (exact match in content/title)
      - Hybrid (vector + keyword, scores combined)
      - Metadata filtering (source_type, tenant scope)
    """

    async def retrieve(
        self,
        query: str,
        tenant_id: str | None = None,
        source_types: list[str] | None = None,
        top_k: int = 5,
        method: str = "hybrid",
    ) -> RetrievalResult:
        """Retrieve relevant knowledge chunks for a query.

        Args:
            query: Natural language query
            tenant_id: Scope to tenant-specific + global chunks
            source_types: Filter by source type (regulation, investigation, etc.)
            top_k: Number of results to return
            method: "vector", "keyword", or "hybrid"
        """
        if method == "keyword":
            return await self._keyword_search(query, tenant_id, source_types, top_k)
        elif method == "vector":
            return await self._vector_search(query, tenant_id, source_types, top_k)
        else:
            return await self._hybrid_search(query, tenant_id, source_types, top_k)

    async def _vector_search(
        self, query: str, tenant_id: str | None,
        source_types: list[str] | None, top_k: int,
    ) -> RetrievalResult:
        """Semantic similarity search via pgvector."""
        from apps.ai_agents.embedding_service import embed_text, EmbeddingTaskType

        query_vector = await embed_text(query, EmbeddingTaskType.RETRIEVAL_QUERY)

        factory = get_session_factory()
        async with factory() as session:
            # Build pgvector cosine distance query
            vector_str = "[" + ",".join(str(v) for v in query_vector) + "]"

            where_clauses = []
            # Tenant scoping: include global (NULL tenant) + tenant-specific
            if tenant_id:
                where_clauses.append(
                    f"(tenant_id IS NULL OR tenant_id = '{tenant_id}')"
                )
            if source_types:
                types_str = ",".join(f"'{t}'" for t in source_types)
                where_clauses.append(f"source_type IN ({types_str})")

            where_sql = " AND ".join(where_clauses) if where_clauses else "TRUE"

            sql = text(f"""
                SELECT id, title, content, source_type, source_ref, metadata,
                       1 - (embedding <=> :vector::vector) as similarity
                FROM knowledge_chunks
                WHERE {where_sql} AND embedding IS NOT NULL
                ORDER BY embedding <=> :vector::vector
                LIMIT :limit
            """)

            result = await session.execute(sql, {
                "vector": vector_str,
                "limit": top_k * 2,  # Over-fetch for filtering
            })
            rows = result.all()

        chunks = [
            ChunkResult(
                chunk_id=str(row.id),
                title=row.title,
                content=row.content,
                source_type=row.source_type,
                source_ref=row.source_ref,
                relevance_score=round(float(row.similarity), 4),
                metadata=row.metadata or {},
            )
            for row in rows
        ][:top_k]

        return RetrievalResult(
            query=query,
            chunks=chunks,
            total_candidates=len(rows),
            retrieval_method="vector",
        )

    async def _keyword_search(
        self, query: str, tenant_id: str | None,
        source_types: list[str] | None, top_k: int,
    ) -> RetrievalResult:
        """Full-text keyword search in content and title."""
        from packages.schemas.embeddings import KnowledgeChunk

        factory = get_session_factory()
        async with factory() as session:
            conditions = [
                or_(
                    KnowledgeChunk.content.ilike(f"%{query}%"),
                    KnowledgeChunk.title.ilike(f"%{query}%"),
                )
            ]
            if tenant_id:
                conditions.append(or_(
                    KnowledgeChunk.tenant_id.is_(None),
                    KnowledgeChunk.tenant_id == uuid.UUID(tenant_id),
                ))
            if source_types:
                conditions.append(KnowledgeChunk.source_type.in_(source_types))

            stmt = (
                select(KnowledgeChunk)
                .where(and_(*conditions))
                .limit(top_k)
            )
            result = await session.execute(stmt)
            rows = list(result.scalars().all())

        chunks = [
            ChunkResult(
                chunk_id=str(row.id),
                title=row.title,
                content=row.content,
                source_type=row.source_type,
                source_ref=row.source_ref,
                relevance_score=0.7,  # Flat score for keyword matches
                metadata=row.metadata_ or {},
            )
            for row in rows
        ]

        return RetrievalResult(
            query=query,
            chunks=chunks,
            total_candidates=len(rows),
            retrieval_method="keyword",
        )

    async def _hybrid_search(
        self, query: str, tenant_id: str | None,
        source_types: list[str] | None, top_k: int,
    ) -> RetrievalResult:
        """Combine vector and keyword results, deduplicate, re-score."""
        vector_result = await self._vector_search(query, tenant_id, source_types, top_k)
        keyword_result = await self._keyword_search(query, tenant_id, source_types, top_k)

        # Merge and deduplicate by chunk_id
        seen: dict[str, ChunkResult] = {}
        for chunk in vector_result.chunks:
            seen[chunk.chunk_id] = chunk
        for chunk in keyword_result.chunks:
            if chunk.chunk_id in seen:
                # Boost score for chunks found by both methods
                existing = seen[chunk.chunk_id]
                boosted = ChunkResult(
                    chunk_id=existing.chunk_id,
                    title=existing.title,
                    content=existing.content,
                    source_type=existing.source_type,
                    source_ref=existing.source_ref,
                    relevance_score=min(1.0, existing.relevance_score + 0.15),
                    metadata=existing.metadata,
                )
                seen[chunk.chunk_id] = boosted
            else:
                seen[chunk.chunk_id] = chunk

        # Sort by score descending, take top_k
        combined = sorted(seen.values(), key=lambda c: c.relevance_score, reverse=True)

        return RetrievalResult(
            query=query,
            chunks=combined[:top_k],
            total_candidates=len(combined),
            retrieval_method="hybrid",
        )
