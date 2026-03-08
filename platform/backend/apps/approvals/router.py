"""Approval Engine — maker-checker dual control for sensitive operations.

Provides a reusable approval workflow for:
  - High-value payouts
  - Manual risk overrides
  - API key rotation
  - Webhook secret changes
  - Recon write-offs
  - Compliance resolutions
  - User/role escalation

Every approval stores full audit trail with maker, checker, timestamps.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from fastapi import APIRouter, Depends, Header, Query, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import Column, DateTime, String, Text, Boolean, Integer
from sqlalchemy.dialects.postgresql import JSONB, UUID

from packages.core.models import APIResponse, BaseDTO
from packages.db.base import Base, TimestampMixin


# ─── Schema ───

class ApprovalRequest(Base, TimestampMixin):
    """A pending approval request requiring checker sign-off."""
    __tablename__ = "approval_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    # What needs approval
    resource_type = Column(String(100), nullable=False, index=True,
                           comment="payout | risk_override | api_key | webhook | recon_writeoff | role_change")
    resource_id = Column(String(200), nullable=False)
    action = Column(String(100), nullable=False, comment="create | update | delete | execute | override")

    # Maker info
    maker_id = Column(UUID(as_uuid=True), nullable=False)
    maker_reason = Column(Text, nullable=True)

    # Full payload snapshot for auditing
    payload = Column(JSONB, nullable=False, server_default='{}')

    # Approval state
    status = Column(String(20), nullable=False, default="pending", index=True,
                    comment="pending | approved | rejected | expired | cancelled")

    # Checker info (populated on approval/rejection)
    checker_id = Column(UUID(as_uuid=True), nullable=True)
    checker_reason = Column(Text, nullable=True)
    decided_at = Column(DateTime(timezone=True), nullable=True)

    # Policy
    required_approvers = Column(Integer, default=1, comment="Number of approvals needed")
    expiry_hours = Column(Integer, default=24, comment="Auto-expire after N hours")
    priority = Column(String(20), default="normal", comment="low | normal | high | critical")


# ─── DTOs ───

class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class CreateApprovalRequest(BaseModel):
    resource_type: str = Field(..., description="Type: payout, risk_override, api_key, etc.")
    resource_id: str = Field(..., description="ID of the resource")
    action: str = Field(default="execute", description="Action: create, update, delete, execute, override")
    reason: str | None = Field(None, description="Maker's justification")
    payload: dict[str, Any] = Field(default_factory=dict, description="Snapshot of what's being approved")
    priority: str = Field(default="normal")


class ReviewApprovalRequest(BaseModel):
    decision: str = Field(..., description="approved or rejected")
    reason: str | None = Field(None, description="Checker's reason")


class ApprovalDTO(BaseDTO):
    id: str
    resource_type: str
    resource_id: str
    action: str
    status: str
    maker_id: str
    maker_reason: str | None
    priority: str
    created_at: datetime
    checker_id: str | None = None
    checker_reason: str | None = None
    decided_at: datetime | None = None


# ─── Router ───

router = APIRouter()


@router.post("/request", response_model=APIResponse[ApprovalDTO])
async def create_approval(
    body: CreateApprovalRequest,
    x_tenant_id: str = Header(...),
    x_user_id: str = Header(...),
):
    """Create a new approval request (maker action).

    The maker submits a request that requires checker sign-off
    before the action is executed.
    """
    from packages.db.engine import get_session_factory

    approval_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    record = ApprovalRequest(
        id=approval_id,
        tenant_id=uuid.UUID(x_tenant_id),
        resource_type=body.resource_type,
        resource_id=body.resource_id,
        action=body.action,
        maker_id=uuid.UUID(x_user_id),
        maker_reason=body.reason,
        payload=body.payload,
        status=ApprovalStatus.PENDING.value,
        priority=body.priority,
    )

    factory = get_session_factory()
    async with factory() as session:
        session.add(record)
        await session.commit()

    return APIResponse.ok(ApprovalDTO(
        id=str(approval_id),
        resource_type=body.resource_type,
        resource_id=body.resource_id,
        action=body.action,
        status="pending",
        maker_id=x_user_id,
        maker_reason=body.reason,
        priority=body.priority,
        created_at=now,
    ))


@router.post("/{approval_id}/review", response_model=APIResponse[ApprovalDTO])
async def review_approval(
    approval_id: str,
    body: ReviewApprovalRequest,
    x_tenant_id: str = Header(...),
    x_user_id: str = Header(...),
):
    """Review an approval request (checker action).

    Checker must be different from maker (dual control enforcement).
    """
    from sqlalchemy import select
    from packages.db.engine import get_session_factory

    factory = get_session_factory()
    async with factory() as session:
        stmt = select(ApprovalRequest).where(
            ApprovalRequest.id == uuid.UUID(approval_id),
            ApprovalRequest.tenant_id == uuid.UUID(x_tenant_id),
        )
        result = await session.execute(stmt)
        record = result.scalar_one_or_none()

        if not record:
            raise HTTPException(status_code=404, detail="Approval request not found")

        if record.status != ApprovalStatus.PENDING.value:
            raise HTTPException(status_code=409, detail=f"Request already {record.status}")

        # Dual control: checker must be different from maker
        if str(record.maker_id) == x_user_id:
            raise HTTPException(status_code=403, detail="Checker must be different from maker (dual control)")

        if body.decision not in ("approved", "rejected"):
            raise HTTPException(status_code=400, detail="Decision must be 'approved' or 'rejected'")

        now = datetime.now(timezone.utc)
        record.status = body.decision
        record.checker_id = uuid.UUID(x_user_id)
        record.checker_reason = body.reason
        record.decided_at = now

        await session.commit()

    return APIResponse.ok(ApprovalDTO(
        id=approval_id,
        resource_type=record.resource_type,
        resource_id=record.resource_id,
        action=record.action,
        status=body.decision,
        maker_id=str(record.maker_id),
        maker_reason=record.maker_reason,
        priority=record.priority,
        created_at=record.created_at,
        checker_id=x_user_id,
        checker_reason=body.reason,
        decided_at=now,
    ))


@router.get("/pending", response_model=APIResponse[list[ApprovalDTO]])
async def list_pending(
    x_tenant_id: str = Header(...),
    resource_type: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    """List pending approval requests for this tenant."""
    from sqlalchemy import select
    from packages.db.engine import get_session_factory

    factory = get_session_factory()
    async with factory() as session:
        stmt = (
            select(ApprovalRequest)
            .where(
                ApprovalRequest.tenant_id == uuid.UUID(x_tenant_id),
                ApprovalRequest.status == ApprovalStatus.PENDING.value,
            )
            .order_by(ApprovalRequest.created_at.desc())
            .limit(limit)
        )
        if resource_type:
            stmt = stmt.where(ApprovalRequest.resource_type == resource_type)

        result = await session.execute(stmt)
        rows = list(result.scalars().all())

    return APIResponse.ok([
        ApprovalDTO(
            id=str(r.id),
            resource_type=r.resource_type,
            resource_id=r.resource_id,
            action=r.action,
            status=r.status,
            maker_id=str(r.maker_id),
            maker_reason=r.maker_reason,
            priority=r.priority,
            created_at=r.created_at,
            checker_id=str(r.checker_id) if r.checker_id else None,
            checker_reason=r.checker_reason,
            decided_at=r.decided_at,
        )
        for r in rows
    ])
