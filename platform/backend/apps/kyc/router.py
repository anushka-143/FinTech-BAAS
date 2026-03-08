"""KYC/KYB case management — India-specific.

Supported Indian KYC document types:
  Individual: Aadhaar, PAN, Voter ID, Driving License, Passport
  Business:   GSTIN, CIN, FSSAI, Udyam (MSME)
  Additional: Bank account (penny drop), DigiLocker

Per RBI KYC Master Directions 2025:
  - Aadhaar is not mandatory for general KYC
  - DigiLocker e-documents are legally valid
  - Periodic re-KYC: 2 years (high risk), 8 years (medium), 10 years (low)
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from enum import StrEnum

from fastapi import APIRouter, Depends, Header, UploadFile, File, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.errors import NotFoundError, ValidationError
from packages.core.models import APIResponse, BaseDTO
from packages.db.engine import get_session
from packages.events.outbox import write_outbox_event
from packages.events.schemas import KYCCaseCreated, KYCCaseVerified
from packages.providers.va_kyc_adapter import KYCAdapter
from packages.providers.base import ProviderKYCVerifyRequest
from packages.schemas.kyc import (
    KYCCase,
    KYCDecision,
    KYCDocument,
    KYCExtraction,
    KYCValidationCheck,
)

router = APIRouter()


# ─── Indian document type enum ───

class IndianDocumentType(StrEnum):
    AADHAAR = "aadhaar"
    PAN = "pan"
    VOTER_ID = "voter_id"
    DRIVING_LICENSE = "driving_license"
    PASSPORT = "passport"
    GSTIN = "gstin"
    CIN = "cin"
    FSSAI = "fssai"
    UDYAM = "udyam"
    BANK_ACCOUNT = "bank_account"


INDIVIDUAL_DOCS = {
    IndianDocumentType.AADHAAR,
    IndianDocumentType.PAN,
    IndianDocumentType.VOTER_ID,
    IndianDocumentType.DRIVING_LICENSE,
    IndianDocumentType.PASSPORT,
}

BUSINESS_DOCS = {
    IndianDocumentType.GSTIN,
    IndianDocumentType.CIN,
    IndianDocumentType.FSSAI,
    IndianDocumentType.UDYAM,
}


# ─── Schemas ───

class CreateCaseRequest(BaseModel):
    case_type: str = Field(..., pattern="^(kyc|kyb)$")
    entity_name: str = Field(..., min_length=1, max_length=255)
    entity_type: str = Field(
        ...,
        pattern="^(individual|sole_proprietorship|partnership|pvt_ltd|llp|public_ltd|trust|society|huf)$",
    )
    entity_id: str | None = None
    pan_number: str | None = Field(None, description="PAN of the entity (mandatory for KYB)")
    aadhaar_number: str | None = Field(None, description="Aadhaar of the individual (optional per RBI 2025)")
    gstin: str | None = Field(None, description="GSTIN for business entities")


class CaseResponse(BaseDTO):
    id: uuid.UUID
    case_type: str
    entity_name: str
    entity_type: str
    status: str
    risk_level: str | None
    created_at: datetime


class DocumentResponse(BaseDTO):
    id: uuid.UUID
    case_id: uuid.UUID
    document_type: str
    file_name: str
    file_size_bytes: int
    status: str
    created_at: datetime


class VerifyDocumentRequest(BaseModel):
    document_type: IndianDocumentType
    document_number: str = Field(..., min_length=1, max_length=50)
    name: str | None = None
    dob: str | None = Field(None, description="Date of birth in YYYY-MM-DD format")
    ifsc: str | None = Field(None, description="IFSC code for bank account verification")


class VerificationResponse(BaseDTO):
    document_type: str
    is_valid: bool
    matched_name: str | None
    details: dict
    verified_at: datetime


class DecisionRequest(BaseModel):
    decision: str = Field(..., pattern="^(approved|rejected|escalated)$")
    reason: str | None = None
    risk_score: float | None = None


class DecisionResponse(BaseDTO):
    id: uuid.UUID
    case_id: uuid.UUID
    decision: str
    decision_type: str
    reason: str | None
    risk_score: float | None
    created_at: datetime


# ─── Endpoints ───

@router.post("/cases", response_model=APIResponse[CaseResponse])
async def create_case(
    body: CreateCaseRequest,
    session: AsyncSession = Depends(get_session),
    x_tenant_id: str = Header(...),
):
    """Create a KYC (individual) or KYB (business) case."""
    tenant_id = uuid.UUID(x_tenant_id)

    # For KYB, GSTIN or CIN is typically required
    if body.case_type == "kyb" and body.entity_type not in ("individual", "sole_proprietorship", "huf"):
        if not body.gstin and not body.entity_id:
            pass  # Allow creation without GSTIN, can be added later

    case = KYCCase(
        tenant_id=tenant_id,
        case_type=body.case_type,
        entity_name=body.entity_name,
        entity_type=body.entity_type,
        entity_id=body.entity_id,
        status="created",
    )
    session.add(case)
    await session.flush()

    await write_outbox_event(
        session,
        KYCCaseCreated(
            tenant_id=str(tenant_id),
            case_id=str(case.id),
            case_type=body.case_type,
            entity_name=body.entity_name,
        ),
    )

    return APIResponse.ok(CaseResponse.model_validate(case))


@router.get("/cases/{case_id}", response_model=APIResponse[CaseResponse])
async def get_case(
    case_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    x_tenant_id: str = Header(...),
):
    stmt = select(KYCCase).where(
        KYCCase.id == case_id,
        KYCCase.tenant_id == uuid.UUID(x_tenant_id),
    )
    result = await session.execute(stmt)
    case = result.scalar_one_or_none()
    if not case:
        raise NotFoundError("KYCCase", str(case_id))
    return APIResponse.ok(CaseResponse.model_validate(case))


@router.post("/cases/{case_id}/documents", response_model=APIResponse[DocumentResponse])
async def upload_document(
    case_id: uuid.UUID,
    document_type: IndianDocumentType = Query(...),
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    x_tenant_id: str = Header(...),
):
    """Upload a KYC document (Aadhaar, PAN, Voter ID, DL, Passport, GSTIN, etc.)."""
    tenant_id = uuid.UUID(x_tenant_id)

    stmt = select(KYCCase).where(KYCCase.id == case_id, KYCCase.tenant_id == tenant_id)
    result = await session.execute(stmt)
    case = result.scalar_one_or_none()
    if not case:
        raise NotFoundError("KYCCase", str(case_id))

    content = await file.read()
    content_hash = hashlib.sha256(content).hexdigest()
    file_key = f"kyc/{tenant_id}/{case_id}/{uuid.uuid4()}/{file.filename}"

    doc = KYCDocument(
        tenant_id=tenant_id,
        case_id=case_id,
        document_type=document_type.value,
        file_key=file_key,
        file_name=file.filename or "unnamed",
        file_size_bytes=len(content),
        mime_type=file.content_type or "application/octet-stream",
        content_hash=content_hash,
        status="uploaded",
    )
    session.add(doc)

    if case.status == "created":
        case.status = "documents_uploaded"

    await session.flush()
    return APIResponse.ok(DocumentResponse.model_validate(doc))


@router.post(
    "/cases/{case_id}/verify-document",
    response_model=APIResponse[VerificationResponse],
)
async def verify_document(
    case_id: uuid.UUID,
    body: VerifyDocumentRequest,
    session: AsyncSession = Depends(get_session),
    x_tenant_id: str = Header(...),
):
    """Verify a document against Indian government registries.

    Routes to the appropriate registry based on document_type.
    """
    tenant_id = uuid.UUID(x_tenant_id)

    stmt = select(KYCCase).where(KYCCase.id == case_id, KYCCase.tenant_id == tenant_id)
    result = await session.execute(stmt)
    case = result.scalar_one_or_none()
    if not case:
        raise NotFoundError("KYCCase", str(case_id))

    adapter = KYCAdapter()
    additional = {}
    if body.ifsc:
        additional["ifsc"] = body.ifsc

    provider_response = await adapter.verify_document(
        ProviderKYCVerifyRequest(
            document_type=body.document_type.value,
            document_number=body.document_number,
            name=body.name,
            dob=body.dob,
            additional_params=additional,
        )
    )

    # Record the verification check
    check = KYCValidationCheck(
        case_id=case_id,
        tenant_id=tenant_id,
        check_type=f"kyc_{body.document_type.value}_verification",
        check_provider="platform",
        result="pass" if provider_response.is_valid else "fail",
        details={
            **provider_response.details,
            "matched_name": provider_response.matched_name,
            "raw_response": provider_response.raw_response,
        },
    )
    session.add(check)
    await session.flush()

    return APIResponse.ok(
        VerificationResponse(
            document_type=body.document_type.value,
            is_valid=provider_response.is_valid,
            matched_name=provider_response.matched_name,
            details=provider_response.details,
            verified_at=datetime.now(timezone.utc),
        )
    )


@router.post("/cases/{case_id}/trigger-ocr", response_model=APIResponse[CaseResponse])
async def trigger_ocr(
    case_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    x_tenant_id: str = Header(...),
):
    """Trigger OCR extraction on uploaded documents (Temporal workflow in production)."""
    tenant_id = uuid.UUID(x_tenant_id)
    stmt = select(KYCCase).where(KYCCase.id == case_id, KYCCase.tenant_id == tenant_id)
    result = await session.execute(stmt)
    case = result.scalar_one_or_none()
    if not case:
        raise NotFoundError("KYCCase", str(case_id))

    case.status = "verification_in_progress"
    await session.flush()
    return APIResponse.ok(CaseResponse.model_validate(case))


@router.post("/cases/{case_id}/decision", response_model=APIResponse[DecisionResponse])
async def record_decision(
    case_id: uuid.UUID,
    body: DecisionRequest,
    session: AsyncSession = Depends(get_session),
    x_tenant_id: str = Header(...),
    x_user_id: str = Header(None),
):
    """Record a KYC decision (maker-checker enforced in production)."""
    tenant_id = uuid.UUID(x_tenant_id)
    stmt = select(KYCCase).where(KYCCase.id == case_id, KYCCase.tenant_id == tenant_id)
    result = await session.execute(stmt)
    case = result.scalar_one_or_none()
    if not case:
        raise NotFoundError("KYCCase", str(case_id))

    decision = KYCDecision(
        case_id=case_id,
        tenant_id=tenant_id,
        decision=body.decision,
        decided_by=uuid.UUID(x_user_id) if x_user_id else None,
        decision_type="manual",
        reason=body.reason,
        risk_score=body.risk_score,
    )
    session.add(decision)

    case.status = body.decision
    case.decision_at = datetime.now(timezone.utc)

    if body.decision == "approved":
        await write_outbox_event(
            session,
            KYCCaseVerified(
                tenant_id=str(tenant_id),
                case_id=str(case_id),
                decision="approved",
                risk_level=case.risk_level or "low",
            ),
        )

    await session.flush()
    return APIResponse.ok(DecisionResponse.model_validate(decision))


@router.get("/document-types", response_model=APIResponse[dict])
async def list_document_types():
    """List all supported Indian KYC/KYB document types."""
    return APIResponse.ok({
        "individual": [
            {"id": "aadhaar", "name": "Aadhaar Card", "issuer": "UIDAI", "required": False,
             "note": "Not mandatory per RBI KYC Master Directions 2025"},
            {"id": "pan", "name": "PAN Card", "issuer": "Income Tax Department", "required": True},
            {"id": "voter_id", "name": "Voter ID", "issuer": "Election Commission of India"},
            {"id": "driving_license", "name": "Driving License", "issuer": "RTO"},
            {"id": "passport", "name": "Indian Passport", "issuer": "Ministry of External Affairs"},
            {"id": "bank_account", "name": "Bank Account (Penny Drop)", "issuer": "Banks"},
        ],
        "business": [
            {"id": "gstin", "name": "GSTIN", "issuer": "GST Council", "format": "15-digit alphanumeric"},
            {"id": "cin", "name": "CIN", "issuer": "MCA / ROC", "format": "21-digit alphanumeric"},
            {"id": "fssai", "name": "FSSAI License", "issuer": "FSSAI"},
            {"id": "udyam", "name": "Udyam Registration", "issuer": "Ministry of MSME"},
        ],
        "re_kyc_periods": {
            "high_risk": "2 years",
            "medium_risk": "8 years",
            "low_risk": "10 years",
        },
    })


@router.post("/cases/{case_id}/liveness")
async def check_liveness(
    case_id: uuid.UUID,
    selfie: UploadFile = File(...),
    document_photo: UploadFile | None = File(None),
    active_challenge: str | None = Query(None, description="blink|turn_left|turn_right|smile|nod"),
    session: AsyncSession = Depends(get_session),
    x_tenant_id: str = Header(...),
):
    """Run liveness detection + deepfake defense on a selfie.

    Pipeline:
    1. Passive liveness (texture, depth, moire, reflection)
    2. Active challenge (optional — blink/turn/smile)
    3. Deepfake detection (GAN fingerprints, temporal coherence)
    4. Face-to-document matching (if document_photo provided)
    """
    from apps.kyc.liveness import LivenessDetector

    tenant_id = uuid.UUID(x_tenant_id)
    stmt = select(KYCCase).where(KYCCase.id == case_id, KYCCase.tenant_id == tenant_id)
    result = await session.execute(stmt)
    case = result.scalar_one_or_none()
    if not case:
        raise NotFoundError("KYCCase", str(case_id))

    selfie_bytes = await selfie.read()
    doc_bytes = await document_photo.read() if document_photo else None

    detector = LivenessDetector()
    liveness_result = await detector.assess_liveness(
        frame_data=selfie_bytes,
        document_photo=doc_bytes,
        active_challenge=active_challenge,
    )

    return APIResponse.ok({
        "assessment_id": liveness_result.assessment_id,
        "is_live": liveness_result.is_live,
        "overall_confidence": liveness_result.overall_confidence,
        "spoof_type": liveness_result.spoof_type,
        "face_match_score": liveness_result.face_match_score,
        "checks": [
            {
                "type": c.check_type,
                "passed": c.passed,
                "confidence": c.confidence,
            }
            for c in liveness_result.checks
        ],
        "warnings": liveness_result.warnings,
    })
