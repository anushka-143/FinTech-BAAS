"""Immutable audit log service — append-only, tenant-scoped."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Header, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.models import APIResponse, BaseDTO, PaginatedResponse, PaginationParams
from packages.db.engine import get_session
from packages.schemas.audit import AuditEvent

router = APIRouter()


# ─── Schemas ───

class AuditEventResponse(BaseDTO):
    id: uuid.UUID
    actor_type: str
    actor_id: str
    action: str
    resource_type: str
    resource_id: str
    description: str | None
    ip_address: str | None
    request_id: str | None
    created_at: datetime


# ─── Endpoints ───

@router.get("/events", response_model=APIResponse[PaginatedResponse[AuditEventResponse]])
async def list_audit_events(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    resource_type: str | None = Query(None),
    action: str | None = Query(None),
    actor_id: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
    x_tenant_id: str = Header(...),
):
    tenant_id = uuid.UUID(x_tenant_id)
    base_query = select(AuditEvent).where(AuditEvent.tenant_id == tenant_id)
    count_query = select(func.count(AuditEvent.id)).where(AuditEvent.tenant_id == tenant_id)

    if resource_type:
        base_query = base_query.where(AuditEvent.resource_type == resource_type)
        count_query = count_query.where(AuditEvent.resource_type == resource_type)
    if action:
        base_query = base_query.where(AuditEvent.action == action)
        count_query = count_query.where(AuditEvent.action == action)
    if actor_id:
        base_query = base_query.where(AuditEvent.actor_id == actor_id)
        count_query = count_query.where(AuditEvent.actor_id == actor_id)

    # Total count
    total_result = await session.execute(count_query)
    total = total_result.scalar() or 0

    # Fetch page
    stmt = (
        base_query
        .order_by(AuditEvent.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await session.execute(stmt)
    events = list(result.scalars().all())

    return APIResponse.ok(
        PaginatedResponse.create(
            items=[AuditEventResponse.model_validate(e) for e in events],
            total=total,
            page=page,
            page_size=page_size,
        )
    )
