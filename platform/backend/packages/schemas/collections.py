"""Collections and virtual accounts tables."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base, TenantMixin


COLLECTION_STATUS_ENUM = Enum(
    "created",
    "active",
    "payment_detected",
    "pending_recon",
    "settled",
    "reversed",
    "failed",
    name="collection_status_enum",
)


class VirtualAccount(Base, TenantMixin):
    __tablename__ = "virtual_accounts"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    va_number: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    bank_code: Mapped[str] = mapped_column(String(20), nullable=False)
    ifsc: Mapped[str] = mapped_column(String(11), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    purpose: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(
        Enum("active", "frozen", "closed", name="va_status_enum"),
        nullable=False,
        server_default="active",
    )
    ledger_account_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    is_permanent: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    expected_amount: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSONB, server_default=text("'{}'::jsonb")
    )


class VirtualAccountMapping(Base, TenantMixin):
    __tablename__ = "virtual_account_mappings"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    virtual_account_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(255), nullable=False)


class CollectionTransaction(Base, TenantMixin):
    __tablename__ = "collection_transactions"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    virtual_account_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default="INR")
    sender_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sender_account: Mapped[str | None] = mapped_column(String(40), nullable=True)
    sender_ifsc: Mapped[str | None] = mapped_column(String(11), nullable=True)
    utr: Mapped[str | None] = mapped_column(String(30), nullable=True)
    payment_mode: Mapped[str | None] = mapped_column(String(20), nullable=True)
    status: Mapped[str] = mapped_column(
        COLLECTION_STATUS_ENUM, nullable=False, server_default="payment_detected"
    )
    provider_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    journal_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSONB, server_default=text("'{}'::jsonb")
    )


class CollectionCallback(Base):
    """Raw inbound callback from provider — immutable audit of what was received."""

    __tablename__ = "collection_callbacks"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    raw_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    signature: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False)
    processing_status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="pending"
    )
    transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class CollectionReconciliationRun(Base, TenantMixin):
    __tablename__ = "collection_reconciliation_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    statement_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    total_statement_entries: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    matched_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    unmatched_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="pending"
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
