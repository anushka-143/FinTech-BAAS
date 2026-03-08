"""Outbox publisher — polls unpublished events and emits to Redpanda.

This runs as a background task or a separate worker process.
Uses SELECT ... FOR UPDATE SKIP LOCKED for safe concurrent polling.

Usage: python -m packages.events.outbox_publisher
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.settings import get_settings
from packages.db.engine import get_session_factory
from packages.observability.setup import get_logger, setup_logging
from packages.schemas.events import OutboxEvent

logger = get_logger("outbox_publisher")

POLL_INTERVAL_SECONDS = 1
BATCH_SIZE = 100


async def publish_batch(session: AsyncSession) -> int:
    """Fetch and publish a batch of unpublished outbox events.

    Dispatches events via Redis pub/sub if REDIS_URL is configured.
    Falls back to log-only mode otherwise.
    """
    # Fetch unpublished events with row-level lock
    stmt = (
        select(OutboxEvent)
        .where(OutboxEvent.published_at.is_(None))
        .order_by(OutboxEvent.created_at)
        .limit(BATCH_SIZE)
        .with_for_update(skip_locked=True)
    )
    result = await session.execute(stmt)
    events = list(result.scalars().all())

    if not events:
        return 0

    # Try Redis pub/sub dispatch
    redis_client = None
    settings = get_settings()
    if settings.redis_url:
        try:
            import redis.asyncio as aioredis
            redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)
        except Exception:
            redis_client = None

    for event in events:
        payload = json.dumps({
            "event_type": event.event_type,
            "topic": event.topic,
            "aggregate_id": event.aggregate_id,
            "tenant_id": str(event.tenant_id),
            "payload": event.payload if isinstance(event.payload, dict) else json.loads(event.payload or "{}"),
            "created_at": event.created_at.isoformat() if event.created_at else None,
        })

        if redis_client:
            try:
                await redis_client.publish(f"events:{event.topic}", payload)
            except Exception:
                logger.warning("redis_publish_failed", event_type=event.event_type)

        logger.info(
            "publishing_event",
            event_type=event.event_type,
            topic=event.topic,
            aggregate_id=event.aggregate_id,
            tenant_id=str(event.tenant_id),
        )
        event.published_at = datetime.now(timezone.utc)

    if redis_client:
        await redis_client.aclose()

    await session.commit()
    return len(events)


async def run_publisher() -> None:
    """Main publisher loop — polls and publishes forever."""
    setup_logging()
    logger.info("outbox_publisher_starting")

    factory = get_session_factory()

    while True:
        try:
            async with factory() as session:
                count = await publish_batch(session)
                if count > 0:
                    logger.info("batch_published", count=count)
        except Exception:
            logger.exception("outbox_publisher_error")

        await asyncio.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    asyncio.run(run_publisher())
