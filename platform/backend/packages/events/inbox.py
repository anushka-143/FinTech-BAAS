"""Enhanced Outbox/Inbox Pattern — consumer idempotency and inbox deduplication.

The outbox publisher already handles DB → event. This module adds:
  - Inbox pattern for consumers (deduplicate received events)
  - Idempotency keys for critical event processing
  - Dead-letter tracking for failed events
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Column, DateTime, String, Boolean, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from packages.db.base import Base, TimestampMixin


class InboxEvent(Base, TimestampMixin):
    """Tracks received events for consumer idempotency.

    Before processing an event, check if its event_id exists here.
    If it does, skip processing (already handled).
    """
    __tablename__ = "inbox_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id = Column(String(200), nullable=False, unique=True, index=True,
                      comment="Unique event ID from the producer")
    event_type = Column(String(100), nullable=False, index=True)
    source = Column(String(100), nullable=False, comment="Service/module that produced the event")
    consumer = Column(String(100), nullable=False, comment="Service/module consuming the event")

    # Processing state
    processed = Column(Boolean, default=False)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    result = Column(String(50), nullable=True, comment="success | failed | skipped")
    error = Column(Text, nullable=True)

    # Payload snapshot
    payload = Column(JSONB, nullable=False, server_default='{}')


class DeadLetterEvent(Base, TimestampMixin):
    """Events that failed processing beyond retry limit."""
    __tablename__ = "dead_letter_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id = Column(String(200), nullable=False, index=True)
    event_type = Column(String(100), nullable=False)
    source = Column(String(100), nullable=False)
    payload = Column(JSONB, nullable=False, server_default='{}')
    error = Column(Text, nullable=False)
    retry_count = Column(String(10), nullable=False, default="0")
    last_retry_at = Column(DateTime(timezone=True), nullable=True)


class InboxProcessor:
    """Idempotent event processing with inbox deduplication.

    Usage:
        processor = InboxProcessor("webhook-service")
        if not await processor.already_processed(event_id):
            try:
                # Process event
                await processor.mark_processed(event_id, event_type, payload)
            except Exception as e:
                await processor.mark_failed(event_id, event_type, payload, str(e))
    """

    def __init__(self, consumer_name: str):
        self.consumer = consumer_name

    async def already_processed(self, event_id: str) -> bool:
        """Check if an event has already been processed by this consumer."""
        try:
            from sqlalchemy import select
            from packages.db.engine import get_session_factory

            factory = get_session_factory()
            async with factory() as session:
                stmt = select(InboxEvent).where(
                    InboxEvent.event_id == event_id,
                    InboxEvent.consumer == self.consumer,
                    InboxEvent.processed.is_(True),
                )
                result = await session.execute(stmt)
                return result.scalar_one_or_none() is not None
        except Exception:
            return False

    async def mark_processed(
        self, event_id: str, event_type: str, payload: dict, source: str = "unknown",
    ) -> None:
        """Mark an event as successfully processed."""
        from packages.db.engine import get_session_factory

        factory = get_session_factory()
        async with factory() as session:
            record = InboxEvent(
                event_id=event_id,
                event_type=event_type,
                source=source,
                consumer=self.consumer,
                processed=True,
                processed_at=datetime.now(timezone.utc),
                result="success",
                payload=payload,
            )
            session.add(record)
            await session.commit()

    async def mark_failed(
        self, event_id: str, event_type: str, payload: dict, error: str,
        source: str = "unknown", move_to_dlq: bool = False,
    ) -> None:
        """Mark an event as failed. Optionally move to dead letter queue."""
        from packages.db.engine import get_session_factory

        factory = get_session_factory()
        async with factory() as session:
            record = InboxEvent(
                event_id=event_id,
                event_type=event_type,
                source=source,
                consumer=self.consumer,
                processed=True,
                processed_at=datetime.now(timezone.utc),
                result="failed",
                error=error,
                payload=payload,
            )
            session.add(record)

            if move_to_dlq:
                dlq = DeadLetterEvent(
                    event_id=event_id,
                    event_type=event_type,
                    source=source,
                    payload=payload,
                    error=error,
                )
                session.add(dlq)

            await session.commit()
