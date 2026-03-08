"""Reconciliation engine — statement import, matching, break classification."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.errors import NotFoundError
from packages.core.models import APIResponse, BaseDTO
from packages.db.engine import get_session
from packages.events.outbox import write_outbox_event
from packages.events.schemas import ReconBreakDetected
from packages.schemas.recon import ReconItem, ReconRun

router = APIRouter()


# ─── Schemas ───

class CreateReconRunRequest(BaseModel):
    run_type: str = Field(..., min_length=1, max_length=50)
    statement_source: str = Field(..., min_length=1, max_length=100)
    period_start: datetime
    period_end: datetime
    items: list[dict] = Field(default_factory=list)


class ReconRunResponse(BaseDTO):
    id: uuid.UUID
    run_type: str
    statement_source: str
    status: str
    total_entries: int
    matched_count: int
    unmatched_count: int
    break_count: int
    created_at: datetime
    completed_at: datetime | None


class ReconItemResponse(BaseDTO):
    id: uuid.UUID
    side: str
    reference: str
    amount: int
    currency: str
    match_status: str
    break_reason: str | None
    ai_explanation: str | None
    created_at: datetime


# ─── Endpoints ───

@router.post("/runs", response_model=APIResponse[ReconRunResponse])
async def create_recon_run(
    body: CreateReconRunRequest,
    session: AsyncSession = Depends(get_session),
    x_tenant_id: str = Header(...),
):
    tenant_id = uuid.UUID(x_tenant_id)

    run = ReconRun(
        tenant_id=tenant_id,
        run_type=body.run_type,
        statement_source=body.statement_source,
        period_start=body.period_start,
        period_end=body.period_end,
        total_entries=len(body.items),
        status="processing",
    )
    session.add(run)
    await session.flush()

    matched = 0
    unmatched = 0
    breaks = 0

    for item_data in body.items:
        # Match against internal ledger journals
        from packages.schemas.ledger import LedgerJournal
        from sqlalchemy import and_
        from datetime import timedelta

        ext_ref = item_data.get("reference", "")
        ext_amount = item_data.get("amount", 0)
        ext_date = (
            datetime.fromisoformat(item_data["transaction_date"])
            if "transaction_date" in item_data
            else datetime.now(timezone.utc)
        )

        match_status = "unmatched"
        break_reason = None

        if ext_ref:
            # Try exact reference match first
            match_stmt = select(LedgerJournal).where(
                LedgerJournal.tenant_id == tenant_id,
                LedgerJournal.reference == ext_ref,
            )
            match_result = await session.execute(match_stmt)
            matched_journal = match_result.scalar_one_or_none()

            if matched_journal:
                # Check amount match
                if matched_journal.amount == ext_amount:
                    match_status = "matched"
                else:
                    match_status = "break"
                    diff = abs(matched_journal.amount - ext_amount)
                    if diff <= abs(ext_amount) * 0.03:
                        break_reason = "fee_adjustment"
                    else:
                        break_reason = "amount_mismatch"
            else:
                # Try fuzzy match: same amount ± 2 days
                fuzzy_stmt = select(LedgerJournal).where(
                    LedgerJournal.tenant_id == tenant_id,
                    LedgerJournal.amount == ext_amount,
                    LedgerJournal.created_at >= ext_date - timedelta(days=2),
                    LedgerJournal.created_at <= ext_date + timedelta(days=2),
                )
                fuzzy_result = await session.execute(fuzzy_stmt)
                fuzzy_match = fuzzy_result.scalar_one_or_none()
                if fuzzy_match:
                    match_status = "break"
                    break_reason = "timing"
                else:
                    match_status = "unmatched"
                    break_reason = "no_internal_match"

        item = ReconItem(
            run_id=run.id,
            tenant_id=tenant_id,
            side=item_data.get("side", "external"),
            reference=item_data.get("reference", "unknown"),
            amount=item_data.get("amount", 0),
            currency=item_data.get("currency", "INR"),
            transaction_date=datetime.fromisoformat(item_data["transaction_date"])
            if "transaction_date" in item_data
            else datetime.now(timezone.utc),
            match_status=match_status,
            break_reason=break_reason,
            raw_data=item_data,
        )
        session.add(item)

        if break_reason:
            await write_outbox_event(
                session,
                ReconBreakDetected(
                    tenant_id=str(tenant_id),
                    run_id=str(run.id),
                    item_id=str(item.id),
                    break_reason=break_reason,
                    amount_minor=item_data.get("amount", 0),
                ),
            )

    run.matched_count = matched
    run.unmatched_count = unmatched
    run.break_count = breaks
    run.status = "completed"
    run.completed_at = datetime.now(timezone.utc)

    await session.flush()
    return APIResponse.ok(ReconRunResponse.model_validate(run))


@router.get("/runs/{run_id}", response_model=APIResponse[ReconRunResponse])
async def get_recon_run(
    run_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    x_tenant_id: str = Header(...),
):
    stmt = select(ReconRun).where(
        ReconRun.id == run_id,
        ReconRun.tenant_id == uuid.UUID(x_tenant_id),
    )
    result = await session.execute(stmt)
    run = result.scalar_one_or_none()
    if not run:
        raise NotFoundError("ReconRun", str(run_id))
    return APIResponse.ok(ReconRunResponse.model_validate(run))


@router.get("/runs/{run_id}/items", response_model=APIResponse[list[ReconItemResponse]])
async def get_recon_items(
    run_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    x_tenant_id: str = Header(...),
):
    stmt = (
        select(ReconItem)
        .where(
            ReconItem.run_id == run_id,
            ReconItem.tenant_id == uuid.UUID(x_tenant_id),
        )
        .order_by(ReconItem.created_at)
    )
    result = await session.execute(stmt)
    items = list(result.scalars().all())
    return APIResponse.ok([ReconItemResponse.model_validate(i) for i in items])
