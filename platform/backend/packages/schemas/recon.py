"""Reconciliation tables."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base, TenantMixin


class ReconRun(Base, TenantMixin):
    __tablename__ = "recon_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    run_type: Mapped[str] = mapped_column(String(50), nullable=False)
    statement_source: Mapped[str] = mapped_column(String(100), nullable=False)
    statement_file_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    statement_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    period_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    period_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default="pending"
    )
    total_entries: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    matched_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    unmatched_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    break_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    total_amount: Mapped[int] = mapped_column(BigInteger, server_default=text("0"))
    matched_amount: Mapped[int] = mapped_column(BigInteger, server_default=text("0"))
    workflow_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class ReconItem(Base):
    __tablename__ = "recon_items"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    side: Mapped[str] = mapped_column(String(20), nullable=False)
    reference: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default="INR")
    transaction_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    match_status: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default="unmatched"
    )
    matched_with_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    break_reason: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ai_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_data: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
