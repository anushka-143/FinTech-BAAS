"""Payouts API — India-specific.

Supported payment rails (via our banking partner integrations):
  UPI:  up to ₹1,00,000 per txn, 24/7, synchronous
  IMPS: up to ₹5,00,000 per txn, 24/7, synchronous, settled within 1 min
  NEFT: up to ₹1,00,00,000 per txn, banking hours, asynchronous (2-3h batches)
  RTGS: ₹2,00,000 to ₹5,00,00,000 per txn, banking hours, asynchronous

IMPS/NEFT/RTGS require: account_number + ifsc_code
UPI requires: vpa (UPI ID like user@upi)
"""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.models import APIResponse, BaseDTO
from packages.db.engine import get_session

from apps.payouts.service import PayoutService

router = APIRouter()


# ─── Schemas ───

class CreateBeneficiaryRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    account_number: str = Field(..., min_length=1, max_length=40)
    ifsc_code: str | None = Field(None, max_length=11)
    vpa: str | None = Field(None, max_length=255)
    bank_name: str | None = None
    account_type: str = Field(default="savings")


class BeneficiaryResponse(BaseDTO):
    id: uuid.UUID
    name: str
    account_number: str
    ifsc_code: str | None
    vpa: str | None
    is_verified: bool
    created_at: datetime


class CreatePayoutRequest(BaseModel):
    beneficiary_id: uuid.UUID
    source_account_id: uuid.UUID
    amount: int = Field(..., gt=0,description="Amount in minor units (paise)")
    currency: str = Field(default="INR", min_length=3, max_length=3)
    purpose: str = Field(..., min_length=1)
    narration: str | None = None
    rail: str = Field(default="imps", pattern="^(upi|imps|neft|rtgs)$")
    idempotency_key: str = Field(..., min_length=1, max_length=255)


class PayoutResponse(BaseDTO):
    id: uuid.UUID
    status: str
    amount: int
    currency: str
    rail: str
    provider_reference: str | None
    failure_reason: str | None
    sent_at: datetime | None
    completed_at: datetime | None
    created_at: datetime


class PayoutTimelineEntry(BaseDTO):
    from_status: str | None
    to_status: str
    reason: str | None
    actor: str
    created_at: datetime


class ProviderCallbackRequest(BaseModel):
    provider_reference: str
    provider_status: str


# ─── Endpoints ───

@router.post("/beneficiaries", response_model=APIResponse[BeneficiaryResponse])
async def create_beneficiary(
    body: CreateBeneficiaryRequest,
    session: AsyncSession = Depends(get_session),
    x_tenant_id: str = Header(...),
):
    svc = PayoutService(session)
    bene = await svc.create_beneficiary(
        tenant_id=uuid.UUID(x_tenant_id),
        name=body.name,
        account_number=body.account_number,
        ifsc_code=body.ifsc_code,
        vpa=body.vpa,
        bank_name=body.bank_name,
        account_type=body.account_type,
    )
    return APIResponse.ok(BeneficiaryResponse.model_validate(bene))


@router.post("", response_model=APIResponse[PayoutResponse])
async def create_payout(
    body: CreatePayoutRequest,
    session: AsyncSession = Depends(get_session),
    x_tenant_id: str = Header(...),
):
    svc = PayoutService(session)
    payout = await svc.create_payout(
        tenant_id=uuid.UUID(x_tenant_id),
        beneficiary_id=body.beneficiary_id,
        source_account_id=body.source_account_id,
        amount=body.amount,
        currency=body.currency,
        purpose=body.purpose,
        narration=body.narration,
        rail=body.rail,
        idempotency_key=body.idempotency_key,
    )
    return APIResponse.ok(PayoutResponse.model_validate(payout))


@router.get("/{payout_id}", response_model=APIResponse[PayoutResponse])
async def get_payout(
    payout_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    x_tenant_id: str = Header(...),
):
    svc = PayoutService(session)
    payout = await svc.get_payout(payout_id, uuid.UUID(x_tenant_id))
    return APIResponse.ok(PayoutResponse.model_validate(payout))


@router.get("/{payout_id}/timeline", response_model=APIResponse[list[PayoutTimelineEntry]])
async def get_payout_timeline(
    payout_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    x_tenant_id: str = Header(...),
):
    svc = PayoutService(session)
    timeline = await svc.get_timeline(payout_id, uuid.UUID(x_tenant_id))
    return APIResponse.ok([PayoutTimelineEntry.model_validate(t) for t in timeline])


@router.post("/provider-callbacks", response_model=APIResponse[PayoutResponse])
async def provider_callback(
    body: ProviderCallbackRequest,
    session: AsyncSession = Depends(get_session),
    x_tenant_id: str = Header(...),
):
    svc = PayoutService(session)
    payout = await svc.process_provider_callback(
        tenant_id=uuid.UUID(x_tenant_id),
        provider_reference=body.provider_reference,
        provider_status=body.provider_status,
    )
    return APIResponse.ok(PayoutResponse.model_validate(payout))
