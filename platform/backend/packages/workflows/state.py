"""Workflow State Design — schemas, retry policies, compensation for stateful workflows.

Defines formal workflow contracts for:
  - Payout orchestration
  - KYC review pipeline
  - Recon runs
  - Webhook delivery
  - Document processing

Each workflow has:
  - Input schema
  - State snapshots
  - Activity retry policy
  - Compensating actions
  - Timeout classes
  - Human-in-the-loop pause/resume
  - Replay-safe activity design
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import StrEnum
from typing import Any

from sqlalchemy import Column, DateTime, String, Text, Integer, Float
from sqlalchemy.dialects.postgresql import JSONB, UUID

from packages.db.base import Base, TimestampMixin


# ─── Schema ───

class WorkflowExecution(Base, TimestampMixin):
    """A single workflow execution with full state tracking."""
    __tablename__ = "workflow_executions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    workflow_type = Column(String(100), nullable=False, index=True,
                          comment="payout_orchestration | kyc_review | recon_run | webhook_delivery | doc_processing")
    workflow_version = Column(String(20), nullable=False, default="1.0")

    # State
    status = Column(String(30), nullable=False, default="pending", index=True,
                    comment="pending | running | paused | waiting_human | completed | failed | compensating | cancelled")
    current_step = Column(String(100), nullable=True)
    step_index = Column(Integer, default=0)

    # Input/output
    input_payload = Column(JSONB, nullable=False, server_default='{}')
    state_snapshot = Column(JSONB, nullable=False, server_default='{}',
                           comment="Accumulated state from all completed activities")
    output_payload = Column(JSONB, nullable=True)

    # Timing
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    deadline_at = Column(DateTime(timezone=True), nullable=True)
    paused_at = Column(DateTime(timezone=True), nullable=True)

    # Error tracking
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)

    # Correlation
    resource_type = Column(String(50), nullable=True)
    resource_id = Column(String(200), nullable=True, index=True)
    parent_workflow_id = Column(UUID(as_uuid=True), nullable=True)
    idempotency_key = Column(String(200), nullable=True, unique=True)


class WorkflowActivity(Base, TimestampMixin):
    """An individual activity/step within a workflow execution."""
    __tablename__ = "workflow_activities"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    activity_name = Column(String(100), nullable=False)
    activity_type = Column(String(50), nullable=False,
                           comment="action | decision | human_task | compensation | wait")

    # State
    status = Column(String(20), nullable=False, default="pending",
                    comment="pending | running | completed | failed | skipped | compensated")
    input_data = Column(JSONB, nullable=False, server_default='{}')
    output_data = Column(JSONB, nullable=True)

    # Timing
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    duration_ms = Column(Float, nullable=True)

    # Retry
    retry_count = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)

    # Human-in-the-loop
    assigned_to = Column(UUID(as_uuid=True), nullable=True)
    human_input = Column(JSONB, nullable=True)


# ─── Retry Policy Definitions ───

class TimeoutClass(StrEnum):
    FAST = "fast"        # 5 seconds — API calls, cache lookups
    STANDARD = "standard"  # 30 seconds — DB operations, provider calls
    SLOW = "slow"        # 5 minutes — OCR, AI analysis
    BATCH = "batch"      # 1 hour — recon runs, report generation
    HUMAN = "human"      # 24 hours — manual review, approval


@dataclass
class ActivityRetryPolicy:
    """Retry configuration per activity type."""
    max_retries: int = 3
    initial_delay_seconds: float = 1.0
    backoff_multiplier: float = 2.0
    max_delay_seconds: float = 300.0
    timeout_class: TimeoutClass = TimeoutClass.STANDARD
    non_retryable_errors: list[str] = field(default_factory=lambda: [
        "INVALID_INPUT", "INSUFFICIENT_FUNDS", "POLICY_DENIED",
    ])

    @property
    def timeout_seconds(self) -> float:
        return {
            TimeoutClass.FAST: 5,
            TimeoutClass.STANDARD: 30,
            TimeoutClass.SLOW: 300,
            TimeoutClass.BATCH: 3600,
            TimeoutClass.HUMAN: 86400,
        }[self.timeout_class]


# ─── Workflow Definitions ───

@dataclass
class WorkflowStep:
    """A step in a workflow definition."""
    name: str
    activity_type: str  # "action" | "decision" | "human_task" | "compensation" | "wait"
    handler: str  # Dotted path to handler function
    retry_policy: ActivityRetryPolicy = field(default_factory=ActivityRetryPolicy)
    compensation_handler: str | None = None
    requires_human: bool = False
    timeout_class: TimeoutClass = TimeoutClass.STANDARD


@dataclass
class WorkflowDefinition:
    """Complete workflow definition with steps and policies."""
    name: str
    version: str
    steps: list[WorkflowStep]
    max_duration_seconds: int = 86400  # 24 hours default
    on_failure: str = "compensate"  # "compensate" | "retry" | "pause" | "fail"


# ─── Pre-defined workflow definitions ───

PAYOUT_WORKFLOW = WorkflowDefinition(
    name="payout_orchestration",
    version="1.0",
    steps=[
        WorkflowStep("validate_input", "action", "payouts.validate",
                      retry_policy=ActivityRetryPolicy(max_retries=0, timeout_class=TimeoutClass.FAST)),
        WorkflowStep("check_policy", "decision", "policy.evaluate_payout",
                      retry_policy=ActivityRetryPolicy(max_retries=1, timeout_class=TimeoutClass.FAST)),
        WorkflowStep("check_balance", "action", "ledger.check_balance",
                      retry_policy=ActivityRetryPolicy(max_retries=2, timeout_class=TimeoutClass.STANDARD)),
        WorkflowStep("risk_assessment", "action", "risk.assess_payout",
                      retry_policy=ActivityRetryPolicy(max_retries=1, timeout_class=TimeoutClass.STANDARD)),
        WorkflowStep("maker_checker", "human_task", "approvals.request_approval",
                      retry_policy=ActivityRetryPolicy(timeout_class=TimeoutClass.HUMAN),
                      requires_human=True,
                      compensation_handler="approvals.cancel_approval"),
        WorkflowStep("hold_funds", "action", "ledger.hold_funds",
                      retry_policy=ActivityRetryPolicy(max_retries=2, timeout_class=TimeoutClass.STANDARD),
                      compensation_handler="ledger.release_hold"),
        WorkflowStep("dispatch_to_provider", "action", "payouts.dispatch",
                      retry_policy=ActivityRetryPolicy(max_retries=3, timeout_class=TimeoutClass.SLOW),
                      compensation_handler="payouts.reverse"),
        WorkflowStep("confirm_settlement", "action", "payouts.confirm",
                      retry_policy=ActivityRetryPolicy(max_retries=5, timeout_class=TimeoutClass.SLOW),
                      compensation_handler="payouts.reverse"),
        WorkflowStep("post_journal", "action", "ledger.post_journal",
                      retry_policy=ActivityRetryPolicy(max_retries=3, timeout_class=TimeoutClass.STANDARD)),
        WorkflowStep("send_webhook", "action", "webhooks.deliver",
                      retry_policy=ActivityRetryPolicy(max_retries=5, timeout_class=TimeoutClass.STANDARD)),
    ],
    on_failure="compensate",
)

KYC_REVIEW_WORKFLOW = WorkflowDefinition(
    name="kyc_review",
    version="1.0",
    steps=[
        WorkflowStep("ingest_documents", "action", "kyc.ingest_documents",
                      retry_policy=ActivityRetryPolicy(timeout_class=TimeoutClass.STANDARD)),
        WorkflowStep("ocr_extraction", "action", "document_ai.extract",
                      retry_policy=ActivityRetryPolicy(max_retries=2, timeout_class=TimeoutClass.SLOW)),
        WorkflowStep("liveness_check", "action", "kyc.check_liveness",
                      retry_policy=ActivityRetryPolicy(timeout_class=TimeoutClass.STANDARD)),
        WorkflowStep("sanctions_screening", "action", "risk.screen_sanctions",
                      retry_policy=ActivityRetryPolicy(timeout_class=TimeoutClass.STANDARD)),
        WorkflowStep("cross_reference", "action", "kyc.cross_reference_docs",
                      retry_policy=ActivityRetryPolicy(timeout_class=TimeoutClass.FAST)),
        WorkflowStep("ai_review", "action", "ai.review_kyc_case",
                      retry_policy=ActivityRetryPolicy(timeout_class=TimeoutClass.SLOW)),
        WorkflowStep("decision", "decision", "decisions.evaluate_kyc",
                      retry_policy=ActivityRetryPolicy(timeout_class=TimeoutClass.FAST)),
        WorkflowStep("human_review", "human_task", "cases.assign_for_review",
                      retry_policy=ActivityRetryPolicy(timeout_class=TimeoutClass.HUMAN),
                      requires_human=True),
        WorkflowStep("final_decision", "action", "kyc.record_decision",
                      retry_policy=ActivityRetryPolicy(timeout_class=TimeoutClass.FAST)),
    ],
    on_failure="pause",
)

RECON_WORKFLOW = WorkflowDefinition(
    name="recon_run",
    version="1.0",
    steps=[
        WorkflowStep("load_internal", "action", "recon.load_internal_txns",
                      retry_policy=ActivityRetryPolicy(timeout_class=TimeoutClass.BATCH)),
        WorkflowStep("load_external", "action", "recon.load_external_statement",
                      retry_policy=ActivityRetryPolicy(timeout_class=TimeoutClass.BATCH)),
        WorkflowStep("match_transactions", "action", "recon.match",
                      retry_policy=ActivityRetryPolicy(timeout_class=TimeoutClass.BATCH)),
        WorkflowStep("classify_breaks", "action", "recon.classify_breaks",
                      retry_policy=ActivityRetryPolicy(timeout_class=TimeoutClass.STANDARD)),
        WorkflowStep("ai_analysis", "action", "ai.analyze_recon_breaks",
                      retry_policy=ActivityRetryPolicy(timeout_class=TimeoutClass.SLOW)),
        WorkflowStep("create_cases", "action", "cases.create_from_breaks",
                      retry_policy=ActivityRetryPolicy(timeout_class=TimeoutClass.STANDARD)),
    ],
    on_failure="pause",
)

WEBHOOK_DELIVERY_WORKFLOW = WorkflowDefinition(
    name="webhook_delivery",
    version="1.0",
    steps=[
        WorkflowStep("serialize_payload", "action", "webhooks.serialize",
                      retry_policy=ActivityRetryPolicy(max_retries=0, timeout_class=TimeoutClass.FAST)),
        WorkflowStep("sign_payload", "action", "webhooks.sign",
                      retry_policy=ActivityRetryPolicy(max_retries=0, timeout_class=TimeoutClass.FAST)),
        WorkflowStep("deliver", "action", "webhooks.http_deliver",
                      retry_policy=ActivityRetryPolicy(
                          max_retries=8,
                          initial_delay_seconds=10,
                          backoff_multiplier=3.0,
                          max_delay_seconds=21600,  # 6 hours max
                          timeout_class=TimeoutClass.STANDARD,
                      )),
        WorkflowStep("record_delivery", "action", "webhooks.record_result",
                      retry_policy=ActivityRetryPolicy(timeout_class=TimeoutClass.FAST)),
    ],
    on_failure="retry",
)

DOC_PROCESSING_WORKFLOW = WorkflowDefinition(
    name="doc_processing",
    version="1.0",
    steps=[
        WorkflowStep("validate_upload", "action", "documents.validate",
                      retry_policy=ActivityRetryPolicy(timeout_class=TimeoutClass.FAST)),
        WorkflowStep("virus_scan", "action", "documents.scan_virus",
                      retry_policy=ActivityRetryPolicy(timeout_class=TimeoutClass.STANDARD)),
        WorkflowStep("compute_hash", "action", "documents.hash",
                      retry_policy=ActivityRetryPolicy(timeout_class=TimeoutClass.FAST)),
        WorkflowStep("store_object", "action", "documents.store",
                      retry_policy=ActivityRetryPolicy(timeout_class=TimeoutClass.STANDARD)),
        WorkflowStep("ocr_extract", "action", "document_ai.extract",
                      retry_policy=ActivityRetryPolicy(timeout_class=TimeoutClass.SLOW)),
        WorkflowStep("embed_content", "action", "knowledge.embed_document",
                      retry_policy=ActivityRetryPolicy(timeout_class=TimeoutClass.SLOW)),
    ],
    on_failure="pause",
)


# ─── Registry ───

WORKFLOW_REGISTRY: dict[str, WorkflowDefinition] = {
    "payout_orchestration": PAYOUT_WORKFLOW,
    "kyc_review": KYC_REVIEW_WORKFLOW,
    "recon_run": RECON_WORKFLOW,
    "webhook_delivery": WEBHOOK_DELIVERY_WORKFLOW,
    "doc_processing": DOC_PROCESSING_WORKFLOW,
}


def get_workflow_definition(name: str) -> WorkflowDefinition | None:
    return WORKFLOW_REGISTRY.get(name)
