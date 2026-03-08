"""Collections / Virtual Accounts service — India-specific.

Collection modes:
  - Virtual Accounts (NEFT, RTGS, IMPS inbound via partner banks)
  - UPI Payment Links
  - UPI Dynamic QR Codes

State: CREATED → ACTIVE → PAYMENT_DETECTED → PENDING_RECON → SETTLED | REVERSED | FAILED
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.errors import NotFoundError
from packages.core.models import APIResponse, BaseDTO, PaginatedResponse, PaginationParams
from packages.db.engine import get_session
from packages.events.outbox import write_outbox_event
from packages.events.schemas import CollectionReceived
from packages.providers.va_kyc_adapter import VAAdapter
from packages.providers.base import ProviderVARequest
from packages.schemas.collections import (
    CollectionCallback,
    CollectionTransaction,
    VirtualAccount,
    VirtualAccountMapping,
)

router = APIRouter()


# ─── Schemas ───

class CreateVARequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    bank_code: str = Field(
        default="YESB",
        description="Indian bank code: YESB (Yes Bank), ICIC (ICICI), HDFC, UTIB (Axis), KKBK (Kotak), IDFB (IDFC First)",
    )
    purpose: str | None = None
    is_permanent: bool = True
    expected_amount: int | None = Field(None, description="Expected amount in paise")


class VAResponse(BaseDTO):
    id: uuid.UUID
    va_number: str
    bank_code: str
    ifsc: str
    name: str
    status: str
    is_permanent: bool
    created_at: datetime


class CollectionTxnResponse(BaseDTO):
    id: uuid.UUID
    virtual_account_id: uuid.UUID
    amount: int
    currency: str
    sender_name: str | None
    utr: str | None
    payment_mode: str | None
    status: str
    created_at: datetime


class ProviderCollectionCallback(BaseModel):
    virtual_account_number: str
    amount: int
    currency: str = "INR"
    sender_name: str | None = None
    sender_account: str | None = None
    sender_ifsc: str | None = None
    utr: str | None = None
    payment_mode: str | None = None
    provider_reference: str | None = None


# ─── Endpoints ───

@router.post("/virtual-accounts", response_model=APIResponse[VAResponse])
async def create_virtual_account(
    body: CreateVARequest,
    session: AsyncSession = Depends(get_session),
    x_tenant_id: str = Header(...),
):
    adapter = VAAdapter()
    provider_resp = await adapter.create_virtual_account(
        ProviderVARequest(
            name=body.name,
            bank_code=body.bank_code,
            purpose=body.purpose,
            is_permanent=body.is_permanent,
            expected_amount=body.expected_amount,
        )
    )

    va = VirtualAccount(
        tenant_id=uuid.UUID(x_tenant_id),
        va_number=provider_resp.va_number,
        bank_code=provider_resp.bank_code,
        ifsc=provider_resp.ifsc,
        name=body.name,
        purpose=body.purpose,
        is_permanent=body.is_permanent,
        expected_amount=body.expected_amount,
    )
    session.add(va)
    await session.flush()

    return APIResponse.ok(VAResponse.model_validate(va))


@router.get("/virtual-accounts/{va_id}", response_model=APIResponse[VAResponse])
async def get_virtual_account(
    va_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    x_tenant_id: str = Header(...),
):
    stmt = select(VirtualAccount).where(
        VirtualAccount.id == va_id,
        VirtualAccount.tenant_id == uuid.UUID(x_tenant_id),
    )
    result = await session.execute(stmt)
    va = result.scalar_one_or_none()
    if not va:
        raise NotFoundError("VirtualAccount", str(va_id))
    return APIResponse.ok(VAResponse.model_validate(va))


@router.get(
    "/virtual-accounts/{va_id}/statement",
    response_model=APIResponse[list[CollectionTxnResponse]],
)
async def get_va_statement(
    va_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    x_tenant_id: str = Header(...),
):
    stmt = (
        select(CollectionTransaction)
        .where(
            CollectionTransaction.virtual_account_id == va_id,
            CollectionTransaction.tenant_id == uuid.UUID(x_tenant_id),
        )
        .order_by(CollectionTransaction.created_at.desc())
        .limit(100)
    )
    result = await session.execute(stmt)
    txns = list(result.scalars().all())
    return APIResponse.ok([CollectionTxnResponse.model_validate(t) for t in txns])


@router.post(
    "/provider-callbacks/collections",
    response_model=APIResponse[CollectionTxnResponse],
)
async def ingest_collection_callback(
    body: ProviderCollectionCallback,
    session: AsyncSession = Depends(get_session),
    x_tenant_id: str = Header(...),
):
    """Ingest an inbound collection callback from the provider."""
    tenant_id = uuid.UUID(x_tenant_id)

    # Find the virtual account
    stmt = select(VirtualAccount).where(
        VirtualAccount.va_number == body.virtual_account_number,
        VirtualAccount.tenant_id == tenant_id,
    )
    result = await session.execute(stmt)
    va = result.scalar_one_or_none()
    if not va:
        raise NotFoundError("VirtualAccount", body.virtual_account_number)

    # Store raw callback
    cb = CollectionCallback(
        tenant_id=tenant_id,
        provider="platform",
        raw_payload=body.model_dump(),
        is_verified=True,
    )
    session.add(cb)

    # Create collection transaction
    txn = CollectionTransaction(
        tenant_id=tenant_id,
        virtual_account_id=va.id,
        amount=body.amount,
        currency=body.currency,
        sender_name=body.sender_name,
        sender_account=body.sender_account,
        sender_ifsc=body.sender_ifsc,
        utr=body.utr,
        payment_mode=body.payment_mode,
        provider_reference=body.provider_reference,
        status="payment_detected",
    )
    session.add(txn)
    await session.flush()

    cb.transaction_id = txn.id
    cb.processing_status = "processed"
    cb.processed_at = datetime.now(timezone.utc)

    # Emit domain event
    await write_outbox_event(
        session,
        CollectionReceived(
            tenant_id=str(tenant_id),
            virtual_account_id=str(va.id),
            transaction_id=str(txn.id),
            amount_minor=body.amount,
            currency=body.currency,
            sender_name=body.sender_name or "",
            utr=body.utr or "",
        ),
    )

    return APIResponse.ok(CollectionTxnResponse.model_validate(txn))


# ─── UPI Payment Links ───

class CreateUPILinkRequest(BaseModel):
    amount: int = Field(..., gt=0, le=1_00_000_00, description="Amount in paise (max ₹1,00,000 for UPI)")
    payee_name: str = Field(..., min_length=1, max_length=255)
    payer_vpa: str | None = Field(None, description="Payer's UPI ID (optional)")
    purpose: str = Field(default="payment", max_length=100)
    expiry_minutes: int = Field(default=30, ge=5, le=1440)


class UPILinkResponse(BaseDTO):
    payment_link_id: str
    upi_link: str
    amount: int
    currency: str = "INR"
    status: str
    expires_at: datetime


class CreateUPIQRRequest(BaseModel):
    amount: int = Field(..., gt=0, le=1_00_000_00, description="Amount in paise (max ₹1,00,000 for UPI)")
    payee_name: str = Field(..., min_length=1, max_length=255)
    purpose: str = Field(default="payment", max_length=100)


class UPIQRResponse(BaseDTO):
    qr_code_id: str
    qr_code_data: str
    amount: int
    currency: str = "INR"
    status: str
    created_at: datetime


@router.post("/upi/payment-link", response_model=APIResponse[UPILinkResponse])
async def generate_upi_payment_link(
    body: CreateUPILinkRequest,
    session: AsyncSession = Depends(get_session),
    x_tenant_id: str = Header(...),
):
    """Generate a UPI payment link.

    Supports deep links for PhonePe, GPay, Paytm, BHIM.
    Max amount: ₹1,00,000 per UPI transaction.
    """
    import uuid as _uuid
    from datetime import timedelta

    link_id = f"UPI-{_uuid.uuid4().hex[:10].upper()}"
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=body.expiry_minutes)

    return APIResponse.ok(
        UPILinkResponse(
            payment_link_id=link_id,
            upi_link=f"upi://pay?pa=merchant@ybl&pn={body.payee_name}&am={body.amount / 100}&cu=INR&tn={body.purpose}",
            amount=body.amount,
            status="active",
            expires_at=expires_at,
        )
    )


@router.post("/upi/qr-code", response_model=APIResponse[UPIQRResponse])
async def generate_upi_qr(
    body: CreateUPIQRRequest,
    session: AsyncSession = Depends(get_session),
    x_tenant_id: str = Header(...),
):
    """Generate a dynamic UPI QR code.

    Works with all major UPI apps (PhonePe, GPay, Paytm, BHIM, etc.).
    """
    import uuid as _uuid

    qr_id = f"QR-{_uuid.uuid4().hex[:10].upper()}"

    return APIResponse.ok(
        UPIQRResponse(
            qr_code_id=qr_id,
            qr_code_data=f"upi://pay?pa=merchant@ybl&pn={body.payee_name}&am={body.amount / 100}&cu=INR&tn={body.purpose}",
            amount=body.amount,
            status="active",
            created_at=datetime.now(timezone.utc),
        )
    )
