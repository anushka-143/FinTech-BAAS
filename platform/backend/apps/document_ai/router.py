"""Document AI router — OCR extraction and document processing endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Header, UploadFile, File, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.models import APIResponse, BaseDTO
from packages.db.engine import get_session

from apps.document_ai.service import DocumentAIService, DocumentType

router = APIRouter()


class ExtractionFieldDTO(BaseDTO):
    field_name: str
    value: str
    confidence: float


class ExtractionResultDTO(BaseDTO):
    extraction_id: str
    document_type: str
    classified_as: str
    fields: list[ExtractionFieldDTO]
    tables: list[dict]
    confidence_overall: float
    anomalies: list[str]
    processing_time_ms: float
    processed_at: datetime


@router.post("/extract", response_model=APIResponse[ExtractionResultDTO])
async def extract_document(
    file: UploadFile = File(...),
    document_type: str = Query(None, description="Expected document type (aadhaar, pan, gstin_certificate, bank_statement, etc.)"),
    x_tenant_id: str = Header(...),
):
    """Extract structured data from a document using our AI pipeline.

    Pipeline: quality check → classification → OCR (PP-OCRv5) →
    layout analysis (PP-StructureV3) → field extraction → anomaly detection.
    """
    content = await file.read()
    service = DocumentAIService()
    result = await service.process_document(
        file_content=content,
        file_name=file.filename or "unnamed",
        mime_type=file.content_type or "application/octet-stream",
        expected_type=document_type,
    )

    return APIResponse.ok(
        ExtractionResultDTO(
            extraction_id=result.extraction_id,
            document_type=result.document_type,
            classified_as=result.classified_as,
            fields=[
                ExtractionFieldDTO(
                    field_name=f.field_name,
                    value=f.value,
                    confidence=f.confidence,
                )
                for f in result.fields
            ],
            tables=result.tables,
            confidence_overall=result.confidence_overall,
            anomalies=result.anomalies,
            processing_time_ms=result.processing_time_ms,
            processed_at=result.processed_at,
        )
    )


@router.get("/supported-types", response_model=APIResponse[list[dict]])
async def list_supported_types():
    """List all supported document types for extraction."""
    return APIResponse.ok([
        {"id": t.value, "name": t.name.replace("_", " ").title()}
        for t in DocumentType
    ])
