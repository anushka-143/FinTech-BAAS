"""Webhook management — endpoint CRUD and delivery tracking."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.errors import NotFoundError
from packages.core.models import APIResponse, BaseDTO
from packages.db.engine import get_session
from packages.schemas.webhooks import WebhookDLQ, WebhookDelivery, WebhookEndpoint, WebhookEvent
from packages.security.hmac_util import create_signature

import secrets

router = APIRouter()


# ─── Schemas ───

class CreateWebhookEndpointRequest(BaseModel):
    url: str = Field(..., min_length=1)
    events: list[str] = Field(..., min_length=1)
    description: str | None = None


class WebhookEndpointResponse(BaseDTO):
    id: uuid.UUID
    url: str
    events: list[str]
    description: str | None
    is_active: bool
    failure_count: int
    created_at: datetime


class WebhookEndpointCreatedResponse(WebhookEndpointResponse):
    secret: str = Field(..., description="Signing secret — shown only once")


class WebhookDeliveryResponse(BaseDTO):
    id: uuid.UUID
    event_id: uuid.UUID
    endpoint_id: uuid.UUID
    attempt_number: int
    response_status_code: int | None
    response_time_ms: int | None
    status: str
    created_at: datetime


class WebhookDLQResponse(BaseDTO):
    id: uuid.UUID
    event_type: str
    total_attempts: int
    last_error: str | None
    can_replay: bool
    created_at: datetime


# ─── Endpoints ───

@router.post("/endpoints", response_model=APIResponse[WebhookEndpointCreatedResponse])
async def create_endpoint(
    body: CreateWebhookEndpointRequest,
    session: AsyncSession = Depends(get_session),
    x_tenant_id: str = Header(...),
):
    tenant_id = uuid.UUID(x_tenant_id)
    webhook_secret = f"whsec_{secrets.token_hex(24)}"

    endpoint = WebhookEndpoint(
        tenant_id=tenant_id,
        url=body.url,
        secret=webhook_secret,
        description=body.description,
        events=body.events,
    )
    session.add(endpoint)
    await session.flush()

    resp = WebhookEndpointCreatedResponse(
        id=endpoint.id,
        url=endpoint.url,
        secret=webhook_secret,
        events=body.events,
        description=body.description,
        is_active=True,
        failure_count=0,
        created_at=endpoint.created_at,
    )
    return APIResponse.ok(resp)


@router.get("/endpoints", response_model=APIResponse[list[WebhookEndpointResponse]])
async def list_endpoints(
    session: AsyncSession = Depends(get_session),
    x_tenant_id: str = Header(...),
):
    stmt = (
        select(WebhookEndpoint)
        .where(WebhookEndpoint.tenant_id == uuid.UUID(x_tenant_id))
        .order_by(WebhookEndpoint.created_at.desc())
    )
    result = await session.execute(stmt)
    endpoints = list(result.scalars().all())
    return APIResponse.ok([WebhookEndpointResponse.model_validate(e) for e in endpoints])


@router.delete("/endpoints/{endpoint_id}", response_model=APIResponse[dict])
async def disable_endpoint(
    endpoint_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    x_tenant_id: str = Header(...),
):
    stmt = select(WebhookEndpoint).where(
        WebhookEndpoint.id == endpoint_id,
        WebhookEndpoint.tenant_id == uuid.UUID(x_tenant_id),
    )
    result = await session.execute(stmt)
    endpoint = result.scalar_one_or_none()
    if not endpoint:
        raise NotFoundError("WebhookEndpoint", str(endpoint_id))
    endpoint.is_active = False
    return APIResponse.ok({"disabled": True})


@router.get("/dlq", response_model=APIResponse[list[WebhookDLQResponse]])
async def list_dlq(
    session: AsyncSession = Depends(get_session),
    x_tenant_id: str = Header(...),
):
    stmt = (
        select(WebhookDLQ)
        .where(WebhookDLQ.tenant_id == uuid.UUID(x_tenant_id))
        .order_by(WebhookDLQ.created_at.desc())
        .limit(50)
    )
    result = await session.execute(stmt)
    items = list(result.scalars().all())
    return APIResponse.ok([WebhookDLQResponse.model_validate(i) for i in items])


@router.post("/dlq/{dlq_id}/replay", response_model=APIResponse[dict])
async def replay_dlq_event(
    dlq_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    x_tenant_id: str = Header(...),
):
    stmt = select(WebhookDLQ).where(
        WebhookDLQ.id == dlq_id,
        WebhookDLQ.tenant_id == uuid.UUID(x_tenant_id),
        WebhookDLQ.can_replay.is_(True),
    )
    result = await session.execute(stmt)
    dlq_item = result.scalar_one_or_none()
    if not dlq_item:
        raise NotFoundError("WebhookDLQ", str(dlq_id))

    # In production: re-queue for delivery via Temporal workflow
    dlq_item.can_replay = False
    return APIResponse.ok({"replayed": True, "event_id": str(dlq_item.event_id)})
