"""AI Agents API — platform intelligence endpoints.

Entry points for the AI intelligence layer:
  POST /triage/payout/{payout_id}  — payout failure triage
  POST /review/kyc/{case_id}       — KYC case AI review
  POST /analyze/recon/{break_id}   — recon break analysis
  POST /explain/risk/{alert_id}    — risk alert explanation
  POST /copilot/ops                — ops copilot query
  POST /copilot/developer          — developer integration copilot

Rule: AI recommends, AI does not execute critical actions.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.errors import NotFoundError
from packages.core.models import APIResponse, BaseDTO
from packages.db.engine import get_session
from packages.schemas.kyc import KYCCase, KYCDocument, KYCExtraction

from apps.ai_agents.orchestrator import AIOrchestrator, AITaskType, AIAnalysisResult

router = APIRouter()

orchestrator = AIOrchestrator()


# ─── Shared response ───

class AIEvidenceDTO(BaseDTO):
    source: str
    detail: str
    relevance: str = "supporting"


class AIRecommendationDTO(BaseDTO):
    action: str
    reason: str
    priority: str = "medium"
    requires_approval: bool = False


class AIResultDTO(BaseDTO):
    task_type: str
    summary: str
    confidence: float
    root_cause: str | None
    evidence: list[AIEvidenceDTO]
    recommendations: list[AIRecommendationDTO]
    warnings: list[str]


def _to_dto(result: AIAnalysisResult) -> AIResultDTO:
    return AIResultDTO(
        task_type=result.task_type,
        summary=result.summary,
        confidence=result.confidence,
        root_cause=result.root_cause,
        evidence=[
            AIEvidenceDTO(source=e.source, detail=e.detail, relevance=e.relevance)
            for e in result.evidence
        ],
        recommendations=[
            AIRecommendationDTO(
                action=r.action, reason=r.reason,
                priority=r.priority, requires_approval=r.requires_approval,
            )
            for r in result.recommendations
        ],
        warnings=result.warnings,
    )


# ─── Endpoints ───

@router.post("/triage/payout/{payout_id}", response_model=APIResponse[AIResultDTO])
async def triage_payout(
    payout_id: uuid.UUID,
    x_tenant_id: str = Header(...),
):
    """AI triage for a failed payout — classifies failure, suggests next action."""
    result = await orchestrator.analyze(
        AITaskType.PAYOUT_TRIAGE,
        context={"payout_id": str(payout_id), "error": "Provider timeout", "rail": "neft"},
        tenant_id=x_tenant_id,
    )
    return APIResponse.ok(_to_dto(result))


@router.post("/review/kyc/{case_id}", response_model=APIResponse[AIResultDTO])
async def review_kyc_case(
    case_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    x_tenant_id: str = Header(...),
):
    """AI review of a KYC/KYB case using live case + extraction context from DB."""
    tenant_id = uuid.UUID(x_tenant_id)

    case_stmt = select(KYCCase).where(KYCCase.id == case_id, KYCCase.tenant_id == tenant_id)
    case_result = await session.execute(case_stmt)
    kyc_case = case_result.scalar_one_or_none()
    if not kyc_case:
        raise NotFoundError("KYCCase", str(case_id))

    docs_stmt = select(KYCDocument).where(KYCDocument.case_id == case_id, KYCDocument.tenant_id == tenant_id)
    docs_result = await session.execute(docs_stmt)
    documents = docs_result.scalars().all()

    document_summaries: list[dict] = []
    extracted_fields: list[dict] = []
    confidences: list[float] = []

    for document in documents:
        document_summaries.append(
            {
                "id": str(document.id),
                "type": document.document_type,
                "status": document.status,
                "file_name": document.file_name,
            }
        )

        extraction_stmt = select(KYCExtraction).where(
            KYCExtraction.document_id == document.id,
            KYCExtraction.tenant_id == tenant_id,
        )
        extraction_result = await session.execute(extraction_stmt)
        extraction = extraction_result.scalar_one_or_none()
        if extraction:
            extracted_fields.append(extraction.extracted_fields)
            confidences.append(extraction.confidence_score)

    avg_confidence = round(sum(confidences) / len(confidences), 4) if confidences else 0.0

    result = await orchestrator.analyze(
        AITaskType.KYC_REVIEW,
        context={
            "case_id": str(case_id),
            "case_type": kyc_case.case_type,
            "entity_type": kyc_case.entity_type,
            "entity_name": kyc_case.entity_name,
            "status": kyc_case.status,
            "documents": document_summaries,
            "extracted_fields": extracted_fields,
            "confidence": avg_confidence,
        },
        tenant_id=x_tenant_id,
    )
    return APIResponse.ok(_to_dto(result))


@router.post("/analyze/recon/{break_id}", response_model=APIResponse[AIResultDTO])
async def analyze_recon_break(
    break_id: uuid.UUID,
    x_tenant_id: str = Header(...),
):
    """AI analysis of a reconciliation break — explains mismatch, suggests resolution."""
    result = await orchestrator.analyze(
        AITaskType.RECON_ANALYSIS,
        context={"break_id": str(break_id), "break_type": "amount_mismatch", "amount_diff": 45000},
        tenant_id=x_tenant_id,
    )
    return APIResponse.ok(_to_dto(result))


@router.post("/explain/risk/{alert_id}", response_model=APIResponse[AIResultDTO])
async def explain_risk_alert(
    alert_id: uuid.UUID,
    x_tenant_id: str = Header(...),
):
    """AI explanation of a risk alert — summarizes signals, prioritizes review."""
    result = await orchestrator.analyze(
        AITaskType.RISK_EXPLANATION,
        context={"alert_id": str(alert_id), "alert_type": "high_risk_payout", "score": 0.85},
        tenant_id=x_tenant_id,
    )
    return APIResponse.ok(_to_dto(result))


class CopilotQuery(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)


@router.post("/copilot/ops", response_model=APIResponse[AIResultDTO])
async def ops_copilot(
    body: CopilotQuery,
    x_tenant_id: str = Header(...),
):
    """Ops copilot — answer operational questions about the platform."""
    result = await orchestrator.analyze(
        AITaskType.OPS_COPILOT,
        context={"query": body.query},
        tenant_id=x_tenant_id,
    )
    return APIResponse.ok(_to_dto(result))


@router.post("/copilot/developer", response_model=APIResponse[AIResultDTO])
async def developer_copilot(
    body: CopilotQuery,
    x_tenant_id: str = Header(...),
):
    """Developer copilot — answer API integration and webhook questions."""
    result = await orchestrator.analyze(
        AITaskType.DEVELOPER_COPILOT,
        context={"query": body.query},
        tenant_id=x_tenant_id,
    )
    return APIResponse.ok(_to_dto(result))


class ComplianceCopilotQuery(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000, description="Regulatory/compliance question")
    source_types: list[str] | None = Field(None, description="Filter: regulation, investigation, policy, sanctions")
    context: dict = Field(default_factory=dict, description="Additional context")


class CopilotCitationDTO(BaseDTO):
    source: str
    title: str
    content_snippet: str
    relevance_score: float


class ComplianceCopilotResponse(BaseDTO):
    answer: str
    citations: list[CopilotCitationDTO]
    confidence: float
    tools_used: list[str]
    requires_human_verification: bool


@router.post("/copilot/ask", response_model=APIResponse[ComplianceCopilotResponse])
async def compliance_copilot(
    body: ComplianceCopilotQuery,
    x_tenant_id: str = Header(...),
):
    """Compliance copilot — RAG-powered regulatory Q&A with citations.

    Uses:
      1. RAG retrieval from knowledge base (regulations, PMLA, sanctions context)
      2. Agentic tool calling for live data if needed
      3. Gemini 2.5 Pro for grounded answer generation
    """
    from apps.ai_agents.rag_engine import RAGEngine

    # Step 1: RAG retrieval
    rag = RAGEngine()
    retrieval = await rag.retrieve(
        query=body.question,
        tenant_id=x_tenant_id,
        source_types=body.source_types,
        top_k=5,
        method="hybrid",
    )

    citations = [
        CopilotCitationDTO(
            source=chunk.source_ref,
            title=chunk.title,
            content_snippet=chunk.content[:200],
            relevance_score=chunk.relevance_score,
        )
        for chunk in retrieval.chunks
    ]

    # Step 2: Build context with RAG results for the orchestrator
    rag_context = {
        "query": body.question,
        "retrieved_knowledge": [
            {"title": c.title, "content": c.content, "source": c.source_ref}
            for c in retrieval.chunks
        ],
        "tenant_id": x_tenant_id,
        **body.context,
    }

    # Step 3: Run through orchestrator (may trigger additional tool calls)
    result = await orchestrator.analyze(
        AITaskType.OPS_COPILOT,
        context=rag_context,
        tenant_id=x_tenant_id,
    )

    tools_used = result.metadata.get("tool_calls_executed", [])
    if retrieval.chunks:
        tools_used = ["search_knowledge_base"] + tools_used

    return APIResponse.ok(ComplianceCopilotResponse(
        answer=result.summary,
        citations=citations,
        confidence=result.confidence,
        tools_used=tools_used,
        requires_human_verification=result.requires_human_verification,
    ))

