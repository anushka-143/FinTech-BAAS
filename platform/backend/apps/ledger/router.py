"""Ledger API router."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.models import APIResponse, BaseDTO, PaginatedResponse, PaginationParams
from packages.db.engine import get_session
from packages.schemas.ledger import LedgerAccount, LedgerJournal

from apps.ledger.service import LedgerService

router = APIRouter()


# ─── Request / Response schemas ───

class CreateAccountRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=255)
    account_type: str = Field(..., pattern="^(asset|liability|equity|revenue|expense)$")
    currency: str = Field(default="INR", min_length=3, max_length=3)
    parent_account_id: uuid.UUID | None = None


class AccountResponse(BaseDTO):
    id: uuid.UUID
    code: str
    name: str
    account_type: str
    currency: str
    parent_account_id: uuid.UUID | None
    is_active: bool
    created_at: datetime


class BalanceResponse(BaseDTO):
    account_id: uuid.UUID
    currency: str
    available_balance: int
    reserved_balance: int
    pending_in_balance: int
    pending_out_balance: int
    version: int


class PostingEntry(BaseModel):
    account_id: uuid.UUID
    direction: str = Field(..., pattern="^(debit|credit)$")
    amount: int = Field(..., gt=0)


class CreateJournalRequest(BaseModel):
    reference_type: str = Field(..., min_length=1, max_length=50)
    reference_id: str = Field(..., min_length=1, max_length=255)
    description: str = Field(..., min_length=1)
    entries: list[PostingEntry] = Field(..., min_length=2)
    currency: str = Field(default="INR", min_length=3, max_length=3)
    metadata: dict | None = None


class JournalResponse(BaseDTO):
    id: uuid.UUID
    reference_type: str
    reference_id: str
    description: str
    currency: str
    total_amount: int
    is_reversed: bool
    posted_at: datetime


class CreateHoldRequest(BaseModel):
    account_id: uuid.UUID
    amount: int = Field(..., gt=0)
    reference_type: str = Field(..., min_length=1, max_length=50)
    reference_id: str = Field(..., min_length=1, max_length=255)
    currency: str = Field(default="INR", min_length=3, max_length=3)


class HoldResponse(BaseDTO):
    id: uuid.UUID
    account_id: uuid.UUID
    amount: int
    currency: str
    status: str
    reference_type: str
    reference_id: str
    created_at: datetime


# ─── Endpoints ───

@router.post("/accounts", response_model=APIResponse[AccountResponse])
async def create_account(
    body: CreateAccountRequest,
    session: AsyncSession = Depends(get_session),
    x_tenant_id: str = Header(...),
):
    svc = LedgerService(session)
    account = await svc.create_account(
        tenant_id=uuid.UUID(x_tenant_id),
        code=body.code,
        name=body.name,
        account_type=body.account_type,
        currency=body.currency,
        parent_account_id=body.parent_account_id,
    )
    return APIResponse.ok(AccountResponse.model_validate(account))


@router.get("/accounts/{account_id}/balance", response_model=APIResponse[BalanceResponse])
async def get_balance(
    account_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    x_tenant_id: str = Header(...),
):
    svc = LedgerService(session)
    balance = await svc.get_balance(account_id, uuid.UUID(x_tenant_id))
    return APIResponse.ok(BalanceResponse.model_validate(balance))


@router.post("/journals", response_model=APIResponse[JournalResponse])
async def create_journal(
    body: CreateJournalRequest,
    session: AsyncSession = Depends(get_session),
    x_tenant_id: str = Header(...),
):
    svc = LedgerService(session)
    journal = await svc.create_journal(
        tenant_id=uuid.UUID(x_tenant_id),
        reference_type=body.reference_type,
        reference_id=body.reference_id,
        description=body.description,
        entries=[e.model_dump() for e in body.entries],
        currency=body.currency,
        metadata=body.metadata,
    )
    return APIResponse.ok(JournalResponse.model_validate(journal))


@router.get("/journals/{journal_id}", response_model=APIResponse[JournalResponse])
async def get_journal(
    journal_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    x_tenant_id: str = Header(...),
):
    stmt = select(LedgerJournal).where(
        LedgerJournal.id == journal_id,
        LedgerJournal.tenant_id == uuid.UUID(x_tenant_id),
    )
    result = await session.execute(stmt)
    journal = result.scalar_one_or_none()
    if not journal:
        from packages.core.errors import NotFoundError
        raise NotFoundError("Journal", str(journal_id))
    return APIResponse.ok(JournalResponse.model_validate(journal))


@router.post("/holds", response_model=APIResponse[HoldResponse])
async def create_hold(
    body: CreateHoldRequest,
    session: AsyncSession = Depends(get_session),
    x_tenant_id: str = Header(...),
):
    svc = LedgerService(session)
    hold = await svc.create_hold(
        tenant_id=uuid.UUID(x_tenant_id),
        account_id=body.account_id,
        amount=body.amount,
        reference_type=body.reference_type,
        reference_id=body.reference_id,
        currency=body.currency,
    )
    return APIResponse.ok(HoldResponse.model_validate(hold))


@router.post("/holds/{hold_id}/release", response_model=APIResponse[HoldResponse])
async def release_hold(
    hold_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    x_tenant_id: str = Header(...),
):
    svc = LedgerService(session)
    hold = await svc.release_hold(hold_id, uuid.UUID(x_tenant_id))
    return APIResponse.ok(HoldResponse.model_validate(hold))
