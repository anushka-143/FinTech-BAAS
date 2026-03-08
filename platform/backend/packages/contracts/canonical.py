"""Canonical Data Contracts — provider-agnostic domain models.

Every external provider returns different payloads. These canonical
models normalize them into a single internal representation.

Domains:
  - Payout (request, response, failure reason)
  - Collection (callback, notification)
  - Beneficiary (account, UPI VPA)
  - KYC (document, identity result)
  - Risk (alert, score)
  - Webhook (event envelope)
  - Recon (break, resolution)
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


# ─── Payout Contracts ───

class PayoutRail(StrEnum):
    UPI = "upi"
    IMPS = "imps"
    NEFT = "neft"
    RTGS = "rtgs"


class PayoutState(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"
    REVERSED = "reversed"
    CANCELLED = "cancelled"


class CanonicalPayoutRequest(BaseModel):
    """Provider-agnostic payout request."""
    idempotency_key: str
    amount_paise: int = Field(gt=0)
    currency: str = "INR"
    rail: PayoutRail
    beneficiary: CanonicalBeneficiary | None = None
    narration: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class CanonicalPayoutResponse(BaseModel):
    """Normalized payout response from any provider."""
    provider_ref: str
    status: PayoutState
    amount_paise: int
    rail: PayoutRail
    utr: str | None = None
    failure_code: str | None = None
    failure_reason: str | None = None
    completed_at: datetime | None = None
    raw_provider_response: dict[str, Any] = Field(default_factory=dict)


class CanonicalPayoutFailure(BaseModel):
    """Normalized failure reason."""
    code: str  # INSUFFICIENT_FUNDS | INVALID_BENEFICIARY | BANK_TIMEOUT | PROVIDER_ERROR
    message: str
    is_retryable: bool
    original_provider_code: str = ""
    suggested_action: str = ""  # retry | manual_review | cancel


# ─── Beneficiary Contracts ───

class BeneficiaryType(StrEnum):
    BANK_ACCOUNT = "bank_account"
    UPI_VPA = "upi_vpa"


class CanonicalBeneficiary(BaseModel):
    """Normalized beneficiary."""
    name: str
    type: BeneficiaryType
    account_number: str | None = None
    ifsc_code: str | None = None
    vpa: str | None = None
    bank_name: str | None = None


# ─── Collection Contracts ───

class CollectionState(StrEnum):
    PENDING = "pending"
    RECEIVED = "received"
    SETTLED = "settled"
    FAILED = "failed"
    REFUNDED = "refunded"


class CanonicalCollectionCallback(BaseModel):
    """Normalized collection/payment callback from provider."""
    provider_ref: str
    virtual_account_id: str | None = None
    amount_paise: int
    currency: str = "INR"
    status: CollectionState
    payer_name: str | None = None
    payer_account: str | None = None
    utr: str | None = None
    received_at: datetime | None = None
    raw_provider_response: dict[str, Any] = Field(default_factory=dict)


# ─── KYC Contracts ───

class DocumentType(StrEnum):
    AADHAAR = "aadhaar"
    PAN = "pan"
    PASSPORT = "passport"
    VOTER_ID = "voter_id"
    DRIVING_LICENSE = "driving_license"
    BANK_STATEMENT = "bank_statement"
    GST_CERTIFICATE = "gst_certificate"
    SELFIE = "selfie"


class CanonicalIdentityResult(BaseModel):
    """Normalized identity verification result."""
    document_type: DocumentType
    full_name: str | None = None
    date_of_birth: str | None = None
    document_number: str | None = None
    address: str | None = None
    gender: str | None = None
    face_match_score: float | None = None
    extraction_confidence: float = 0.0
    anomalies: list[str] = Field(default_factory=list)
    raw_extraction: dict[str, Any] = Field(default_factory=dict)


# ─── Risk Contracts ───

class RiskSeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class CanonicalRiskAlert(BaseModel):
    """Normalized risk alert."""
    alert_type: str  # velocity_spike | sanctions_hit | anomaly | policy_violation
    severity: RiskSeverity
    entity_type: str
    entity_id: str
    description: str
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    requires_action: bool = True


# ─── Webhook Contracts ───

class CanonicalWebhookEvent(BaseModel):
    """Normalized webhook event envelope."""
    event_type: str  # payout.completed | collection.received | kyc.approved
    event_id: str
    timestamp: datetime
    resource_type: str
    resource_id: str
    data: dict[str, Any]
    version: str = "1.0"


# ─── Recon Contracts ───

class ReconMatchType(StrEnum):
    EXACT = "exact"
    PARTIAL = "partial"
    UNMATCHED = "unmatched"
    DISPUTED = "disputed"


class CanonicalReconBreak(BaseModel):
    """Normalized reconciliation break."""
    internal_ref: str
    external_ref: str | None = None
    internal_amount_paise: int
    external_amount_paise: int | None = None
    match_type: ReconMatchType
    delta_paise: int = 0
    break_reason: str = ""
    suggested_resolution: str = ""


# ─── Provider Normalization ───

class ProviderNormalizer:
    """Base class for provider-specific payload normalization.

    Each provider adapter extends this to convert provider-specific
    responses into canonical contracts.
    """

    def normalize_payout_response(self, raw: dict) -> CanonicalPayoutResponse:
        raise NotImplementedError

    def normalize_collection_callback(self, raw: dict) -> CanonicalCollectionCallback:
        raise NotImplementedError

    def normalize_failure(self, raw: dict) -> CanonicalPayoutFailure:
        raise NotImplementedError
