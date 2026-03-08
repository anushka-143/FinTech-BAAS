"""Ledger tables — double-entry accounting with holds and settlements.

Invariant: every journal satisfies sum(debits) == sum(credits).
Balances track available, reserved, pending_in, pending_out.
Journal rows are append-only — corrections use compensating entries only.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base, TenantMixin


class LedgerAccount(Base, TenantMixin):
    __tablename__ = "ledger_accounts"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    account_type: Mapped[str] = mapped_column(
        Enum("asset", "liability", "equity", "revenue", "expense", name="account_type_enum"),
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default="INR")
    parent_account_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSONB, server_default=text("'{}'::jsonb")
    )


class LedgerBalance(Base, TenantMixin):
    """Materialized balance for fast reads. Updated transactionally with postings."""

    __tablename__ = "ledger_balances"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default="INR")
    available_balance: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    reserved_balance: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    pending_in_balance: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    pending_out_balance: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    version: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("1")
    )


class LedgerJournal(Base, TenantMixin):
    """Immutable journal entry. sum(debit postings) must equal sum(credit postings)."""

    __tablename__ = "ledger_journals"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    reference_type: Mapped[str] = mapped_column(String(50), nullable=False)
    reference_id: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default="INR")
    total_amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    is_reversed: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    reversed_by_journal_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSONB, server_default=text("'{}'::jsonb")
    )
    posted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class LedgerPosting(Base):
    """Individual debit or credit line within a journal."""

    __tablename__ = "ledger_postings"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    journal_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    direction: Mapped[str] = mapped_column(
        Enum("debit", "credit", name="posting_direction_enum"), nullable=False
    )
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default="INR")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_posting_amount_positive"),
    )


class LedgerHold(Base, TenantMixin):
    """Funds hold / reservation — blocks available_balance until released or captured."""

    __tablename__ = "ledger_holds"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default="INR")
    reference_type: Mapped[str] = mapped_column(String(50), nullable=False)
    reference_id: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        Enum("active", "captured", "released", "expired", name="hold_status_enum"),
        nullable=False,
        server_default="active",
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    captured_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    released_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_hold_amount_positive"),
    )


class LedgerSnapshot(Base, TenantMixin):
    """Point-in-time balance snapshot for auditing and reconciliation."""

    __tablename__ = "ledger_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    available_balance: Mapped[int] = mapped_column(BigInteger, nullable=False)
    reserved_balance: Mapped[int] = mapped_column(BigInteger, nullable=False)
    pending_in_balance: Mapped[int] = mapped_column(BigInteger, nullable=False)
    pending_out_balance: Mapped[int] = mapped_column(BigInteger, nullable=False)
    snapshot_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
