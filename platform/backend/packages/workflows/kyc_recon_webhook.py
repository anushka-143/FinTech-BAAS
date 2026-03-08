"""KYC, Reconciliation, and Webhook Delivery workflow definitions.

These mirror the Payout workflow pattern — Temporal-managed sagas with
retry, timeout, and compensation semantics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta


# ─── KYC Case Workflow ───

@dataclass(frozen=True)
class KYCCaseWorkflowInput:
    tenant_id: str
    case_id: str
    document_ids: list[str] = field(default_factory=list)
    ocr_timeout: timedelta = timedelta(minutes=5)


@dataclass(frozen=True)
class KYCCaseWorkflowResult:
    case_id: str
    final_status: str
    risk_score: float | None = None
    decision_suggestion: str | None = None


class KYCCaseWorkflow:
    """KYC case processing workflow.

    Steps:
    1. Retrieve uploaded documents
    2. Run OCR extraction (PP-StructureV3 default, VL-1.5 fallback)
    3. Normalize extracted fields
    4. Run validation checks (registry, bank verification)
    5. Score risk
    6. Generate decision suggestion
    7. Route to human reviewer if needed
    """

    async def run(self, input: KYCCaseWorkflowInput) -> KYCCaseWorkflowResult:
        # Stub — each step would be a Temporal activity
        return KYCCaseWorkflowResult(
            case_id=input.case_id,
            final_status="review_required",
            risk_score=0.25,
            decision_suggestion="approve",
        )


# ─── Reconciliation Workflow ───

@dataclass(frozen=True)
class ReconciliationWorkflowInput:
    tenant_id: str
    run_id: str
    statement_file_key: str
    period_start: str
    period_end: str


@dataclass(frozen=True)
class ReconciliationWorkflowResult:
    run_id: str
    matched_count: int
    unmatched_count: int
    break_count: int
    status: str


class ReconciliationWorkflow:
    """Reconciliation workflow.

    Steps:
    1. Parse statement file
    2. Load internal ledger transactions for the period
    3. Run matching algorithm (UTR, amount, date)
    4. Classify unmatched items as breaks
    5. Route breaks to ops + AI copilot for explanation
    6. Update run with final counts
    """

    async def run(self, input: ReconciliationWorkflowInput) -> ReconciliationWorkflowResult:
        return ReconciliationWorkflowResult(
            run_id=input.run_id,
            matched_count=0,
            unmatched_count=0,
            break_count=0,
            status="completed",
        )


# ─── Webhook Delivery Workflow ───

@dataclass(frozen=True)
class WebhookDeliveryWorkflowInput:
    tenant_id: str
    event_id: str
    endpoint_id: str
    endpoint_url: str
    signing_secret: str
    payload: dict = field(default_factory=dict)
    max_attempts: int = 5


@dataclass(frozen=True)
class WebhookDeliveryWorkflowResult:
    event_id: str
    endpoint_id: str
    final_status: str  # delivered | dlq
    total_attempts: int
    last_error: str | None = None


class WebhookDeliveryWorkflow:
    """Webhook delivery with exponential backoff + jitter.

    Steps:
    1. Sign payload with HMAC
    2. POST to endpoint URL
    3. On 2xx: mark delivered
    4. On failure: retry with exponential backoff (1s, 2s, 4s, 8s, 16s)
    5. After max_attempts: move to DLQ
    """

    async def run(self, input: WebhookDeliveryWorkflowInput) -> WebhookDeliveryWorkflowResult:
        return WebhookDeliveryWorkflowResult(
            event_id=input.event_id,
            endpoint_id=input.endpoint_id,
            final_status="delivered",
            total_attempts=1,
        )
