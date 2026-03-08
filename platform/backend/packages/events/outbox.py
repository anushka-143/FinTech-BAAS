"""Transactional outbox writer — writes events to the outbox table within the same
DB transaction as business data, ensuring no phantom events or lost events.

A background publisher (outbox_publisher.py) polls unpublished rows and pushes to Redpanda.
"""

from __future__ import annotations

import dataclasses
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from packages.events.schemas import DomainEvent
from packages.schemas.events import OutboxEvent


async def write_outbox_event(
    session: AsyncSession,
    event: DomainEvent,
) -> uuid.UUID:
    """Write a domain event to the outbox within the current transaction."""
    row = OutboxEvent(
        id=uuid.uuid4(),
        tenant_id=uuid.UUID(event.tenant_id) if event.tenant_id else uuid.uuid4(),
        event_type=event.event_type,
        aggregate_type=event.event_type.split(".")[0],
        aggregate_id=getattr(event, "payout_id", "")
        or getattr(event, "case_id", "")
        or getattr(event, "transaction_id", "")
        or getattr(event, "journal_id", "")
        or getattr(event, "alert_id", "")
        or getattr(event, "run_id", "")
        or "",
        payload=dataclasses.asdict(event),
        topic=event.topic,
        partition_key=event.tenant_id,
        published_at=None,
        retry_count=0,
        created_at=datetime.now(timezone.utc),
    )
    session.add(row)
    return row.id
