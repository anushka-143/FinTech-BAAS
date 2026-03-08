"""Real-Time Channel — Server-Sent Events for live dashboard updates.

Provides SSE streams for:
  - Payout status changes
  - KYC queue updates
  - Risk alerts
  - Recon job progress
  - Webhook failures
  - AI investigation completions

Uses in-memory pub/sub. In production, upgrade to Redis pub/sub.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, AsyncGenerator

from fastapi import APIRouter, Header, Query
from fastapi.responses import StreamingResponse


# ─── In-memory event bus (upgrade to Redis pub/sub in production) ───

_subscribers: dict[str, list[asyncio.Queue]] = defaultdict(list)


async def publish_event(tenant_id: str, event_type: str, data: dict[str, Any]) -> None:
    """Publish an event to all subscribers of a tenant."""
    channel = f"tenant:{tenant_id}"
    event = {
        "id": str(uuid.uuid4())[:8],
        "type": event_type,
        "data": data,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    for queue in _subscribers.get(channel, []):
        await queue.put(event)


async def subscribe(tenant_id: str) -> AsyncGenerator[dict, None]:
    """Subscribe to events for a tenant. Yields events as they arrive."""
    channel = f"tenant:{tenant_id}"
    queue: asyncio.Queue = asyncio.Queue()
    _subscribers[channel].append(queue)

    try:
        while True:
            event = await asyncio.wait_for(queue.get(), timeout=30.0)
            yield event
    except asyncio.TimeoutError:
        # Send keepalive
        yield {"type": "keepalive", "data": {}, "timestamp": datetime.now(timezone.utc).isoformat()}
    finally:
        _subscribers[channel].remove(queue)


# ─── SSE Router ───

router = APIRouter()


async def _sse_generator(tenant_id: str, event_filter: str | None) -> AsyncGenerator[str, None]:
    """Generate SSE-formatted events."""
    # Send initial connection event
    yield f"event: connected\ndata: {json.dumps({'tenant_id': tenant_id})}\n\n"

    async for event in subscribe(tenant_id):
        # Filter events if requested
        if event_filter and event.get("type") != event_filter:
            if event.get("type") != "keepalive":
                continue

        event_type = event.get("type", "message")
        data = json.dumps(event.get("data", {}))
        event_id = event.get("id", "")

        yield f"id: {event_id}\nevent: {event_type}\ndata: {data}\n\n"


@router.get("/stream")
async def event_stream(
    x_tenant_id: str = Header(...),
    event_type: str | None = Query(None, description="Filter by event type"),
):
    """SSE endpoint for real-time tenant events.

    Event types:
      - payout.status_changed
      - kyc.case_updated
      - risk.alert_created
      - recon.job_progress
      - webhook.delivery_failed
      - ai.investigation_complete
    """
    return StreamingResponse(
        _sse_generator(x_tenant_id, event_type),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ─── Convenience publishers ───

async def emit_payout_status(tenant_id: str, payout_id: str, status: str, **kwargs):
    await publish_event(tenant_id, "payout.status_changed", {
        "payout_id": payout_id, "status": status, **kwargs,
    })


async def emit_kyc_update(tenant_id: str, case_id: str, status: str, **kwargs):
    await publish_event(tenant_id, "kyc.case_updated", {
        "case_id": case_id, "status": status, **kwargs,
    })


async def emit_risk_alert(tenant_id: str, alert_id: str, severity: str, **kwargs):
    await publish_event(tenant_id, "risk.alert_created", {
        "alert_id": alert_id, "severity": severity, **kwargs,
    })


async def emit_recon_progress(tenant_id: str, run_id: str, progress: float, **kwargs):
    await publish_event(tenant_id, "recon.job_progress", {
        "run_id": run_id, "progress": progress, **kwargs,
    })
