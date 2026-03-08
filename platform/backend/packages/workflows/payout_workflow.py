"""Payout workflow — Temporal-managed payout saga.

Orchestrates the full payout lifecycle with built-in retry, timeout,
and compensation semantics. Much safer than hand-rolled async retries.

Flow:
1. Create payout request
2. Run prechecks (risk, balance, compliance)
3. Reserve funds in ledger
4. Send to payment provider
5. Wait for callback or poll with timeout
6. On success: settle (capture hold, post journal)
7. On failure: reverse (release hold)
8. Notify tenant via webhook
9. Append immutable audit event
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

# Temporal SDK types — these are interface definitions.
# In production: from temporalio import workflow, activity
# Here: stub classes for type-safety without runtime Temporal dependency.


@dataclass(frozen=True)
class PayoutWorkflowInput:
    tenant_id: str
    payout_id: str
    beneficiary_id: str
    source_account_id: str
    amount_minor: int
    currency: str
    rail: str
    purpose: str
    idempotency_key: str
    max_retries: int = 3
    callback_timeout: timedelta = timedelta(minutes=30)
    polling_interval: timedelta = timedelta(seconds=30)


@dataclass(frozen=True)
class PayoutWorkflowResult:
    payout_id: str
    final_status: str  # success | failed_final | reversed
    provider_reference: str | None = None
    failure_reason: str | None = None
    journal_id: str | None = None


# ─── Activity stubs ───

async def run_prechecks(tenant_id: str, payout_id: str) -> dict:
    """Activity: validate beneficiary, check risk score, verify balance."""
    return {"passed": True, "risk_score": 0.1}


async def reserve_funds(tenant_id: str, account_id: str, amount: int, payout_id: str) -> str:
    """Activity: create ledger hold. Returns hold_id."""
    return "hold-stub-id"


async def send_to_provider(tenant_id: str, payout_id: str, rail: str) -> dict:
    """Activity: dispatch payout to payment rail provider."""
    return {"provider_reference": "DCTRO-STUB", "status": "pending"}


async def poll_provider_status(provider_reference: str) -> dict:
    """Activity: poll provider for async payout status."""
    return {"status": "pending"}


async def settle_payout(tenant_id: str, payout_id: str, hold_id: str) -> str:
    """Activity: capture hold, post settlement journal. Returns journal_id."""
    return "journal-stub-id"


async def reverse_payout(tenant_id: str, payout_id: str, hold_id: str) -> None:
    """Activity: release hold, post reversal journal."""
    pass


async def notify_tenant(tenant_id: str, event_type: str, payload: dict) -> None:
    """Activity: send webhook notification to tenant."""
    pass


async def append_audit_event(
    tenant_id: str, action: str, resource_type: str, resource_id: str, details: dict
) -> None:
    """Activity: append immutable audit event."""
    pass


# ─── Workflow Definition ───

class PayoutWorkflow:
    """Temporal workflow for payout orchestration.

    In production, decorate with @workflow.defn and use workflow.execute_activity
    for each step. The Temporal SDK handles retries, timeouts, and compensation
    automatically via activity retry policies and saga compensation.

    This class serves as the workflow contract — the structure is identical to
    what you'd write with the Temporal Python SDK.
    """

    async def run(self, input: PayoutWorkflowInput) -> PayoutWorkflowResult:
        payout_id = input.payout_id
        tenant_id = input.tenant_id
        hold_id: str | None = None

        try:
            # Step 1: Prechecks
            precheck_result = await run_prechecks(tenant_id, payout_id)
            if not precheck_result["passed"]:
                return PayoutWorkflowResult(
                    payout_id=payout_id,
                    final_status="failed_final",
                    failure_reason="Prechecks failed",
                )

            # Step 2: Reserve funds
            hold_id = await reserve_funds(
                tenant_id, input.source_account_id, input.amount_minor, payout_id
            )

            # Step 3: Send to provider
            send_result = await send_to_provider(tenant_id, payout_id, input.rail)
            provider_ref = send_result["provider_reference"]

            if send_result["status"] == "success":
                journal_id = await settle_payout(tenant_id, payout_id, hold_id)
                await notify_tenant(tenant_id, "payout.success", {"payout_id": payout_id})
                await append_audit_event(
                    tenant_id, "payout.settled", "payout", payout_id,
                    {"journal_id": journal_id},
                )
                return PayoutWorkflowResult(
                    payout_id=payout_id,
                    final_status="success",
                    provider_reference=provider_ref,
                    journal_id=journal_id,
                )

            if send_result["status"] == "failed":
                await reverse_payout(tenant_id, payout_id, hold_id)
                return PayoutWorkflowResult(
                    payout_id=payout_id,
                    final_status="failed_final",
                    provider_reference=provider_ref,
                    failure_reason="Provider rejected",
                )

            # Step 4: Wait for callback or poll
            # In production: use workflow.wait_condition with timeout
            for attempt in range(int(input.callback_timeout.total_seconds() / input.polling_interval.total_seconds())):
                status = await poll_provider_status(provider_ref)
                if status["status"] == "success":
                    journal_id = await settle_payout(tenant_id, payout_id, hold_id)
                    await notify_tenant(tenant_id, "payout.success", {"payout_id": payout_id})
                    return PayoutWorkflowResult(
                        payout_id=payout_id,
                        final_status="success",
                        provider_reference=provider_ref,
                        journal_id=journal_id,
                    )
                elif status["status"] == "failed":
                    await reverse_payout(tenant_id, payout_id, hold_id)
                    await notify_tenant(tenant_id, "payout.failed", {"payout_id": payout_id})
                    return PayoutWorkflowResult(
                        payout_id=payout_id,
                        final_status="failed_final",
                        provider_reference=provider_ref,
                        failure_reason="Provider confirmed failure",
                    )
                # Continue polling...

            # Timeout — escalate
            await notify_tenant(tenant_id, "payout.timeout", {"payout_id": payout_id})
            return PayoutWorkflowResult(
                payout_id=payout_id,
                final_status="failed_final",
                provider_reference=provider_ref,
                failure_reason="Callback timeout exceeded",
            )

        except Exception as e:
            # Compensation: release hold if it was created
            if hold_id:
                await reverse_payout(tenant_id, payout_id, hold_id)
            await append_audit_event(
                tenant_id, "payout.error", "payout", payout_id,
                {"error": str(e)},
            )
            raise
