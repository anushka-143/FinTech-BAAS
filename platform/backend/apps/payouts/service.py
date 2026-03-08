"""Payout service — orchestrates the full payout lifecycle.

State machine:
  REQUESTED → PRECHECKED → RESERVED → DISPATCH_PENDING → SENT → PENDING → SUCCESS|FAILED_RETRYABLE|FAILED_FINAL|REVERSED
                                            ↑
                                   DB COMMIT happens HERE
                                   (provider call happens AFTER, in worker)

Why async dispatch:
  The bank provider call MUST happen AFTER the DB commit. If the bank
  says "Success" but our DB crashes during flush(), the money is gone
  and the ledger doesn't know. By committing intent + hold first and
  dispatching via the outbox, we guarantee transactional safety.

Flow:
  1. create_payout() — validate, precheck, reserve funds, emit PayoutDispatchRequested, return immediately
  2. dispatch_payout() — background worker calls bank, records attempt, updates state
  3. process_provider_callback() — async callback from bank updates final state
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.errors import NotFoundError, ValidationError
from packages.events.outbox import write_outbox_event
from packages.events.schemas import (
    PayoutDispatchRequested,
    PayoutFinalized,
    PayoutRequested,
    PayoutSent,
)
from packages.providers.payout_adapter import PayoutAdapter
from packages.providers.base import ProviderPayoutRequest
from packages.schemas.payouts import (
    Beneficiary,
    PayoutAttempt,
    PayoutRequest,
    PayoutStatusHistory,
)

from apps.ledger.service import LedgerService


class PayoutService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._provider = PayoutAdapter()
        self._ledger = LedgerService(session)

    async def create_payout(
        self,
        *,
        tenant_id: uuid.UUID,
        beneficiary_id: uuid.UUID,
        source_account_id: uuid.UUID,
        amount: int,
        currency: str,
        purpose: str,
        narration: str | None,
        rail: str,
        idempotency_key: str,
    ) -> PayoutRequest:
        """Create a payout — commits intent + hold, then dispatches async.

        This method does NOT call the bank. It commits the payout record
        and fund hold to the database, then writes a PayoutDispatchRequested
        event to the outbox. A background worker picks that up and calls
        the bank provider via dispatch_payout().
        """
        # 1. Validate beneficiary exists and belongs to tenant
        bene = await self._get_beneficiary(beneficiary_id, tenant_id)

        # 2. Sync pre-transaction risk check (rules only, <50ms)
        from apps.risk.router import RulesEngine
        risk_result = RulesEngine.evaluate({
            "amount_minor": amount,
            "entity_type": "payout",
            "entity_id": str(beneficiary_id),
            "beneficiary_name": bene.name,
        })
        if risk_result.get("risk_level") == "critical":
            raise ValidationError(
                f"Payout blocked by risk pre-check: {risk_result.get('block_reason', 'risk threshold exceeded')}"
            )

        # 3. Create payout request
        payout = PayoutRequest(
            tenant_id=tenant_id,
            idempotency_key=idempotency_key,
            beneficiary_id=beneficiary_id,
            source_account_id=source_account_id,
            amount=amount,
            currency=currency,
            purpose=purpose,
            narration=narration,
            rail=rail,
            status="requested",
        )
        self._session.add(payout)
        await self._session.flush()

        await self._record_status_change(payout, None, "requested", "Payout created")

        # 4. Precheck
        payout.status = "prechecked"
        await self._record_status_change(payout, "requested", "prechecked", "Prechecks passed")

        # 5. Reserve funds
        hold = await self._ledger.create_hold(
            tenant_id=tenant_id,
            account_id=source_account_id,
            amount=amount,
            reference_type="payout",
            reference_id=str(payout.id),
            currency=currency,
        )
        payout.hold_id = hold.id
        payout.status = "reserved"
        await self._record_status_change(payout, "prechecked", "reserved", "Funds reserved")

        # 6. Set status to dispatch_pending — provider call happens AFTER commit
        payout.status = "dispatch_pending"
        await self._record_status_change(
            payout, "reserved", "dispatch_pending",
            "Intent committed. Awaiting async dispatch to provider.",
        )

        # 7. Emit events — both are written in the SAME transaction as the payout
        await write_outbox_event(
            self._session,
            PayoutRequested(
                tenant_id=str(tenant_id),
                payout_id=str(payout.id),
                beneficiary_id=str(beneficiary_id),
                amount_minor=amount,
                currency=currency,
                rail=rail,
            ),
        )
        await write_outbox_event(
            self._session,
            PayoutDispatchRequested(
                tenant_id=str(tenant_id),
                payout_id=str(payout.id),
                beneficiary_account=bene.account_number or "",
                beneficiary_ifsc=bene.ifsc_code or "",
                beneficiary_vpa=bene.vpa or "",
                beneficiary_name=bene.name,
                amount_minor=amount,
                currency=currency,
                purpose=purpose,
                narration=narration or purpose,
                rail=rail,
                idempotency_key=idempotency_key,
            ),
        )

        # DB COMMIT happens when the session context manager exits.
        # Only AFTER commit does the outbox publisher pick up the dispatch event.
        await self._session.flush()
        return payout

    async def dispatch_payout(
        self,
        *,
        payout_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> PayoutRequest:
        """Called by background worker AFTER DB commit. Makes the bank call.

        This is idempotent — if the payout is already in 'sent' or terminal
        state, it returns without calling the provider again.
        """
        payout = await self.get_payout(payout_id, tenant_id)

        # Idempotency guard — don't re-dispatch
        if payout.status not in ("dispatch_pending", "reserved"):
            return payout

        bene = await self._get_beneficiary(payout.beneficiary_id, tenant_id)

        provider_request = ProviderPayoutRequest(
            beneficiary_account=bene.account_number,
            beneficiary_ifsc=bene.ifsc_code,
            beneficiary_vpa=bene.vpa,
            beneficiary_name=bene.name,
            amount_minor=payout.amount,
            currency=payout.currency,
            purpose=payout.purpose,
            narration=payout.narration or payout.purpose,
            rail=payout.rail,
            reference_id=str(payout.id),
        )

        provider_response = await self._provider.initiate_payout(provider_request)

        # Record attempt
        attempt = PayoutAttempt(
            payout_id=payout.id,
            tenant_id=tenant_id,
            attempt_number=1,
            rail=payout.rail,
            provider_request={
                "account": bene.account_number,
                "amount": payout.amount,
                "rail": payout.rail,
            },
            provider_response=provider_response.raw_response,
            provider_reference=provider_response.provider_reference,
            status=provider_response.status,
        )
        self._session.add(attempt)

        payout.provider_reference = provider_response.provider_reference
        payout.provider_status = provider_response.raw_status
        payout.sent_at = datetime.now(timezone.utc)

        # Map provider response to state machine
        if provider_response.status == "success":
            payout.status = "success"
            payout.completed_at = datetime.now(timezone.utc)
            if payout.hold_id:
                await self._ledger.capture_hold(payout.hold_id, tenant_id)
            await self._record_status_change(
                payout, "dispatch_pending", "success", "Provider confirmed success"
            )
        elif provider_response.status == "failed":
            payout.status = "failed_retryable"
            payout.failure_reason = provider_response.message
            if payout.hold_id:
                await self._ledger.release_hold(payout.hold_id, tenant_id)
            await self._record_status_change(
                payout, "dispatch_pending", "failed_retryable", provider_response.message
            )
        else:
            payout.status = "sent"
            await self._record_status_change(
                payout, "dispatch_pending", "sent", "Sent to provider, awaiting callback"
            )

        await write_outbox_event(
            self._session,
            PayoutSent(
                tenant_id=str(tenant_id),
                payout_id=str(payout.id),
                provider_reference=provider_response.provider_reference or "",
                rail=payout.rail,
            ),
        )

        await self._session.flush()
        return payout

    async def get_payout(
        self, payout_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> PayoutRequest:
        stmt = select(PayoutRequest).where(
            PayoutRequest.id == payout_id,
            PayoutRequest.tenant_id == tenant_id,
        )
        result = await self._session.execute(stmt)
        payout = result.scalar_one_or_none()
        if not payout:
            raise NotFoundError("Payout", str(payout_id))
        return payout

    async def get_timeline(
        self, payout_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> list[PayoutStatusHistory]:
        stmt = (
            select(PayoutStatusHistory)
            .where(
                PayoutStatusHistory.payout_id == payout_id,
                PayoutStatusHistory.tenant_id == tenant_id,
            )
            .order_by(PayoutStatusHistory.created_at)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def process_provider_callback(
        self,
        *,
        tenant_id: uuid.UUID,
        provider_reference: str,
        provider_status: str,
    ) -> PayoutRequest:
        """Process an async callback from the payment provider."""
        stmt = select(PayoutRequest).where(
            PayoutRequest.provider_reference == provider_reference,
            PayoutRequest.tenant_id == tenant_id,
        )
        result = await self._session.execute(stmt)
        payout = result.scalar_one_or_none()
        if not payout:
            raise NotFoundError("Payout", provider_reference)

        old_status = payout.status

        if provider_status in ("success", "SUCCESS"):
            payout.status = "success"
            payout.completed_at = datetime.now(timezone.utc)
            if payout.hold_id:
                await self._ledger.capture_hold(payout.hold_id, tenant_id)
        elif provider_status in ("failed", "FAILED"):
            payout.status = "failed_final"
            payout.completed_at = datetime.now(timezone.utc)
            if payout.hold_id:
                await self._ledger.release_hold(payout.hold_id, tenant_id)
        else:
            payout.status = "pending"

        payout.provider_status = provider_status
        await self._record_status_change(
            payout, old_status, payout.status, f"Provider callback: {provider_status}"
        )

        if payout.status in ("success", "failed_final"):
            await write_outbox_event(
                self._session,
                PayoutFinalized(
                    tenant_id=str(tenant_id),
                    payout_id=str(payout.id),
                    final_status=payout.status,
                    journal_id=str(payout.journal_id or ""),
                ),
            )

        return payout

    async def create_beneficiary(
        self,
        *,
        tenant_id: uuid.UUID,
        name: str,
        account_number: str,
        ifsc_code: str | None,
        vpa: str | None,
        bank_name: str | None,
        account_type: str,
    ) -> Beneficiary:
        bene = Beneficiary(
            tenant_id=tenant_id,
            name=name,
            account_number=account_number,
            ifsc_code=ifsc_code,
            vpa=vpa,
            bank_name=bank_name,
            account_type=account_type,
        )
        self._session.add(bene)
        await self._session.flush()
        return bene

    async def _get_beneficiary(
        self, beneficiary_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> Beneficiary:
        stmt = select(Beneficiary).where(
            Beneficiary.id == beneficiary_id,
            Beneficiary.tenant_id == tenant_id,
            Beneficiary.is_active.is_(True),
        )
        result = await self._session.execute(stmt)
        bene = result.scalar_one_or_none()
        if not bene:
            raise NotFoundError("Beneficiary", str(beneficiary_id))
        return bene

    async def _record_status_change(
        self,
        payout: PayoutRequest,
        from_status: str | None,
        to_status: str,
        reason: str,
    ) -> None:
        history = PayoutStatusHistory(
            payout_id=payout.id,
            tenant_id=payout.tenant_id,
            from_status=from_status,
            to_status=to_status,
            reason=reason,
        )
        self._session.add(history)
