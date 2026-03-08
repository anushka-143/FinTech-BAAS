"""Knowledge Base Ingestion — chunk, embed, and store documents for RAG.

Sources:
  - Regulatory documents (RBI circulars, PMLA rules, FEMA provisions)
  - Sanctions lists (UAPA, MHA, OFAC SDN) with entity context
  - Past investigation decisions
  - Tenant policies
  - API documentation (auto-generated from OpenAPI)

Pipeline:
  document → chunk (800-1200 chars, 200 overlap)
  → mask PII → embed(chunk, RETRIEVAL_DOCUMENT)
  → store in knowledge_chunks table

CLI: python -m apps.ai_agents.knowledge_ingest --source regulations
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from packages.core.settings import get_settings


# Chunking config
CHUNK_SIZE = 1000  # characters
CHUNK_OVERLAP = 200


@dataclass
class Document:
    """A source document to ingest."""
    title: str
    content: str
    source_type: str
    source_ref: str
    tenant_id: str | None = None
    metadata: dict[str, Any] | None = None


@dataclass
class Chunk:
    """A chunked piece of a document."""
    text: str
    title: str
    source_type: str
    source_ref: str
    tenant_id: str | None
    chunk_index: str
    metadata: dict[str, Any]


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping chunks.

    Uses character-based splitting with sentence boundary awareness.
    """
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size

        # Try to break at sentence boundary
        if end < len(text):
            for sep in [". ", ".\n", "\n\n", "\n", " "]:
                last_sep = text[start:end].rfind(sep)
                if last_sep > chunk_size * 0.5:
                    end = start + last_sep + len(sep)
                    break

        chunks.append(text[start:end].strip())
        start = end - overlap

    return [c for c in chunks if c]


def chunk_document(doc: Document) -> list[Chunk]:
    """Split a document into chunks with metadata."""
    text_chunks = chunk_text(doc.content)
    total = len(text_chunks)

    return [
        Chunk(
            text=text,
            title=doc.title,
            source_type=doc.source_type,
            source_ref=doc.source_ref,
            tenant_id=doc.tenant_id,
            chunk_index=f"{i + 1}/{total}",
            metadata=doc.metadata or {},
        )
        for i, text in enumerate(text_chunks)
    ]


async def ingest_document(doc: Document) -> int:
    """Ingest a single document: chunk, embed, store.

    Returns the number of chunks stored.
    """
    from apps.ai_agents.embedding_service import embed_batch, EmbeddingTaskType
    from apps.ai_agents.gemini_client import mask_pii
    from packages.schemas.embeddings import KnowledgeChunk
    from packages.db.engine import get_session_factory

    chunks = chunk_document(doc)
    if not chunks:
        return 0

    # PII-mask before embedding
    texts = [mask_pii(c.text) for c in chunks]

    # Batch embed
    vectors = await embed_batch(texts, EmbeddingTaskType.RETRIEVAL_DOCUMENT)

    # Store in DB
    factory = get_session_factory()
    async with factory() as session:
        for chunk, vector in zip(chunks, vectors):
            record = KnowledgeChunk(
                id=uuid.uuid4(),
                tenant_id=uuid.UUID(chunk.tenant_id) if chunk.tenant_id else None,
                source_type=chunk.source_type,
                source_ref=chunk.source_ref,
                title=chunk.title,
                content=chunk.text,
                embedding=vector,
                metadata_=chunk.metadata,
                chunk_index=chunk.chunk_index,
            )
            session.add(record)
        await session.commit()

    return len(chunks)


async def ingest_batch(docs: list[Document]) -> dict[str, int]:
    """Ingest multiple documents.

    Returns: {"total_docs": N, "total_chunks": M}
    """
    total_chunks = 0
    for doc in docs:
        count = await ingest_document(doc)
        total_chunks += count

    return {"total_docs": len(docs), "total_chunks": total_chunks}


# ─── Built-in knowledge sources ───

def get_sample_regulations() -> list[Document]:
    """Sample Indian fintech regulatory knowledge for seeding."""
    return [
        Document(
            title="RBI Master Direction on KYC",
            content=(
                "Know Your Customer (KYC) norms require regulated entities to verify identity "
                "of customers using officially valid documents. Aadhaar and PAN are mandatory "
                "for individual accounts. Video-based Customer Identification Process (V-CIP) "
                "is permitted as per RBI circular dated January 2020. Re-KYC must be performed "
                "periodically: every 2 years for high-risk, 8 years for medium, 10 years for low. "
                "Beneficial ownership must be established for legal entities with >10% ownership."
            ),
            source_type="regulation",
            source_ref="RBI/2016-17/69",
            metadata={"jurisdiction": "india", "authority": "RBI", "category": "kyc"},
        ),
        Document(
            title="PMLA Act 2002 — Customer Due Diligence",
            content=(
                "Prevention of Money Laundering Act mandates customer due diligence including "
                "identity verification, understanding nature of business, monitoring transactions. "
                "Suspicious Transaction Reports (STR) must be filed with FIU-IND within 7 days. "
                "Cash transactions above INR 10 lakh must be reported. Wire transfers above "
                "INR 50,000 require originator and beneficiary information. Non-compliance "
                "penalties: up to 3x transaction value or INR 5 lakh, whichever is higher."
            ),
            source_type="regulation",
            source_ref="PMLA/2002/Section-12",
            metadata={"jurisdiction": "india", "authority": "FIU-IND", "category": "aml"},
        ),
        Document(
            title="UPI Transaction Limits — NPCI Guidelines",
            content=(
                "UPI per-transaction limit: INR 1,00,000 for most categories. "
                "Exception: INR 2,00,000 for capital markets, insurance premiums, "
                "and loan repayments. INR 5,00,000 for IPOs and RBI retail direct. "
                "Daily limit varies by PSP bank. UPI Lite: max INR 500 per transaction, "
                "INR 2,000 wallet balance. UPI 123PAY for feature phones. "
                "Merchant category codes determine limit applicability."
            ),
            source_type="regulation",
            source_ref="NPCI/UPI/2024-25/Circular-67",
            metadata={"jurisdiction": "india", "authority": "NPCI", "category": "payments"},
        ),
    ]


async def seed_knowledge_base() -> dict[str, int]:
    """Seed the knowledge base with built-in regulatory documents."""
    docs = get_sample_regulations()
    return await ingest_batch(docs)


if __name__ == "__main__":
    import asyncio
    asyncio.run(seed_knowledge_base())
