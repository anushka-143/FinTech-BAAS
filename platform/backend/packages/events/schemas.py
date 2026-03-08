"""Domain event schemas — typed dataclasses for all events that flow through the system."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from packages.core.models import generate_ulid


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class DomainEvent:
    event_id: str = field(default_factory=generate_ulid)
    event_type: str = ""
    tenant_id: str = ""
    timestamp: datetime = field(default_factory=_now)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def topic(self) -> str:
        parts = self.event_type.split(".")
        return f"fintech.{parts[0]}" if parts else "fintech.unknown"


# ─── KYC Events ───
@dataclass(frozen=True, slots=True)
class KYCCaseCreated(DomainEvent):
    event_type: str = "kyc.case.created"
    case_id: str = ""
    case_type: str = ""
    entity_name: str = ""


@dataclass(frozen=True, slots=True)
class KYCCaseParsed(DomainEvent):
    event_type: str = "kyc.case.parsed"
    case_id: str = ""
    document_id: str = ""
    confidence_score: float = 0.0


@dataclass(frozen=True, slots=True)
class KYCCaseVerified(DomainEvent):
    event_type: str = "kyc.case.verified"
    case_id: str = ""
    decision: str = ""
    risk_level: str = ""


# ─── Collection Events ───
@dataclass(frozen=True, slots=True)
class CollectionReceived(DomainEvent):
    event_type: str = "collection.received"
    virtual_account_id: str = ""
    transaction_id: str = ""
    amount_minor: int = 0
    currency: str = "INR"
    sender_name: str = ""
    utr: str = ""


@dataclass(frozen=True, slots=True)
class CollectionReconciled(DomainEvent):
    event_type: str = "collection.reconciled"
    transaction_id: str = ""
    journal_id: str = ""
    status: str = ""


# ─── Payout Events ───
@dataclass(frozen=True, slots=True)
class PayoutRequested(DomainEvent):
    event_type: str = "payout.requested"
    payout_id: str = ""
    beneficiary_id: str = ""
    amount_minor: int = 0
    currency: str = "INR"
    rail: str = ""


@dataclass(frozen=True, slots=True)
class PayoutDispatchRequested(DomainEvent):
    """Emitted after intent + hold are committed. Worker picks this up to call bank."""
    event_type: str = "payout.dispatch.requested"
    payout_id: str = ""
    beneficiary_account: str = ""
    beneficiary_ifsc: str = ""
    beneficiary_vpa: str = ""
    beneficiary_name: str = ""
    amount_minor: int = 0
    currency: str = "INR"
    purpose: str = ""
    narration: str = ""
    rail: str = ""
    idempotency_key: str = ""


@dataclass(frozen=True, slots=True)
class PayoutSent(DomainEvent):
    event_type: str = "payout.sent"
    payout_id: str = ""
    provider_reference: str = ""
    rail: str = ""


@dataclass(frozen=True, slots=True)
class PayoutCallbackReceived(DomainEvent):
    event_type: str = "payout.callback.received"
    payout_id: str = ""
    provider_status: str = ""
    provider_reference: str = ""


@dataclass(frozen=True, slots=True)
class PayoutFinalized(DomainEvent):
    event_type: str = "payout.finalized"
    payout_id: str = ""
    final_status: str = ""
    journal_id: str = ""


# ─── Ledger Events ───
@dataclass(frozen=True, slots=True)
class LedgerJournalPosted(DomainEvent):
    event_type: str = "ledger.journal.posted"
    journal_id: str = ""
    reference_type: str = ""
    reference_id: str = ""
    total_amount: int = 0
    currency: str = "INR"


# ─── Risk Events ───
@dataclass(frozen=True, slots=True)
class RiskAlertCreated(DomainEvent):
    event_type: str = "risk.alert.created"
    alert_id: str = ""
    alert_type: str = ""
    severity: str = ""
    entity_type: str = ""
    entity_id: str = ""


# ─── Reconciliation Events ───
@dataclass(frozen=True, slots=True)
class ReconBreakDetected(DomainEvent):
    event_type: str = "recon.break.detected"
    run_id: str = ""
    item_id: str = ""
    break_reason: str = ""
    amount_minor: int = 0
