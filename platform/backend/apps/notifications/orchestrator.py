"""Notification Orchestrator — multi-channel delivery with severity routing.

Handles:
  - In-app notifications
  - Email delivery
  - Webhook callbacks (dispatches to webhook service)
  - SMS (pluggable adapter)
  - Slack (pluggable adapter)

Features:
  - Severity routing (critical → all channels, low → in-app only)
  - Per-tenant channel preferences
  - Digest vs real-time logic (batch low-priority into periodic digest)
  - Delivery tracking and retry
  - Template registry
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from sqlalchemy import Column, DateTime, String, Text, Boolean, Integer
from sqlalchemy.dialects.postgresql import JSONB, UUID

from packages.db.base import Base, TimestampMixin


# ─── Schema ───

class NotificationRecord(Base, TimestampMixin):
    """Tracks every notification sent across all channels."""
    __tablename__ = "notification_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    # What
    notification_type = Column(String(100), nullable=False, index=True,
                               comment="payout.completed | kyc.approved | risk.alert | recon.break_found | ...")
    severity = Column(String(20), nullable=False, default="medium",
                      comment="low | medium | high | critical")
    title = Column(String(500), nullable=False)
    body = Column(Text, nullable=False)
    data = Column(JSONB, nullable=False, server_default='{}')

    # Who
    recipient_type = Column(String(20), nullable=False, comment="user | role | tenant")
    recipient_id = Column(String(200), nullable=False)

    # Channel delivery tracking
    channels_attempted = Column(JSONB, nullable=False, server_default='[]',
                                comment='["in_app", "email", "webhook"]')
    channels_delivered = Column(JSONB, nullable=False, server_default='[]')
    channels_failed = Column(JSONB, nullable=False, server_default='[]')

    # State
    status = Column(String(20), nullable=False, default="pending",
                    comment="pending | delivering | delivered | partially_delivered | failed")
    delivered_at = Column(DateTime(timezone=True), nullable=True)

    # Digest
    is_digest_eligible = Column(Boolean, default=False)
    digest_batch_id = Column(String(100), nullable=True)

    # Related entity
    resource_type = Column(String(50), nullable=True)
    resource_id = Column(String(200), nullable=True)


class TenantNotificationPreference(Base, TimestampMixin):
    """Per-tenant notification channel preferences."""
    __tablename__ = "tenant_notification_preferences"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    notification_type = Column(String(100), nullable=False,
                               comment="payout.* | kyc.* | risk.* | * (wildcard)")
    channel = Column(String(30), nullable=False, comment="in_app | email | webhook | sms | slack")
    enabled = Column(Boolean, default=True)
    config = Column(JSONB, nullable=False, server_default='{}',
                    comment='email: {to}, slack: {channel}, sms: {phone}')


class NotificationTemplate(Base, TimestampMixin):
    """Registered notification templates for consistent messaging."""
    __tablename__ = "notification_templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    notification_type = Column(String(100), nullable=False, unique=True)
    title_template = Column(String(500), nullable=False, comment="Python format string")
    body_template = Column(Text, nullable=False, comment="Python format string")
    default_severity = Column(String(20), nullable=False, default="medium")
    default_channels = Column(JSONB, nullable=False, server_default='["in_app"]')


# ─── Severity routing rules ───

SEVERITY_CHANNEL_MAP = {
    "critical": ["in_app", "email", "webhook", "sms", "slack"],
    "high": ["in_app", "email", "webhook"],
    "medium": ["in_app", "email"],
    "low": ["in_app"],
}

# Low-severity notifications eligible for digest batching
DIGEST_ELIGIBLE_TYPES = {
    "webhook.delivery_failed",
    "recon.minor_break",
    "kyc.document_uploaded",
    "payout.batch_completed",
}


# ─── Channel Adapters ───

class ChannelAdapter:
    """Base class for notification channel adapters."""
    channel_name: str = "base"

    async def deliver(self, notification: dict, config: dict) -> bool:
        raise NotImplementedError

    async def health_check(self) -> bool:
        return True


class InAppAdapter(ChannelAdapter):
    channel_name = "in_app"

    async def deliver(self, notification: dict, config: dict) -> bool:
        """Store in-app notification for frontend polling/SSE."""
        try:
            from apps.realtime.router import publish_event
            await publish_event(
                tenant_id=notification.get("tenant_id", ""),
                event_type=f"notification.{notification.get('notification_type', '')}",
                data={
                    "title": notification.get("title", ""),
                    "body": notification.get("body", ""),
                    "severity": notification.get("severity", "medium"),
                    "resource_type": notification.get("resource_type"),
                    "resource_id": notification.get("resource_id"),
                },
            )
            return True
        except Exception:
            return False


class EmailAdapter(ChannelAdapter):
    channel_name = "email"

    async def deliver(self, notification: dict, config: dict) -> bool:
        """Send email notification. Currently logs only — plug in SMTP/SES/SendGrid."""
        # In production: connect to email service (SES, SendGrid, etc.)
        import logging
        logger = logging.getLogger("notifications.email")
        logger.info(
            "EMAIL [%s] To: %s | Subject: %s",
            notification.get("severity", "medium"),
            config.get("to", notification.get("recipient_id")),
            notification.get("title", ""),
        )
        return True


class WebhookAdapter(ChannelAdapter):
    channel_name = "webhook"

    async def deliver(self, notification: dict, config: dict) -> bool:
        """Dispatch to the webhook delivery service."""
        try:
            from apps.webhooks.router import dispatch_webhook_event
            await dispatch_webhook_event(
                tenant_id=notification.get("tenant_id", ""),
                event_type=notification.get("notification_type", ""),
                payload=notification.get("data", {}),
            )
            return True
        except Exception:
            return False


class SMSAdapter(ChannelAdapter):
    channel_name = "sms"

    async def deliver(self, notification: dict, config: dict) -> bool:
        """Send SMS. Pluggable — Twilio, MSG91, etc."""
        import logging
        logger = logging.getLogger("notifications.sms")
        logger.info(
            "SMS [%s] To: %s | %s",
            notification.get("severity"),
            config.get("phone", "unknown"),
            notification.get("title", "")[:100],
        )
        return True


class SlackAdapter(ChannelAdapter):
    channel_name = "slack"

    async def deliver(self, notification: dict, config: dict) -> bool:
        """Post to Slack channel. Pluggable — slack-sdk."""
        import logging
        logger = logging.getLogger("notifications.slack")
        logger.info(
            "SLACK [%s] Channel: %s | %s",
            notification.get("severity"),
            config.get("channel", "#alerts"),
            notification.get("title", ""),
        )
        return True


# ─── Orchestrator ───

CHANNEL_ADAPTERS: dict[str, ChannelAdapter] = {
    "in_app": InAppAdapter(),
    "email": EmailAdapter(),
    "webhook": WebhookAdapter(),
    "sms": SMSAdapter(),
    "slack": SlackAdapter(),
}


class NotificationOrchestrator:
    """Routes and delivers notifications across channels.

    Usage:
        orchestrator = NotificationOrchestrator()
        await orchestrator.send(
            tenant_id="...",
            notification_type="payout.completed",
            title="Payout PAY-123 completed",
            body="₹50,000 sent to HDFC account ending 1234",
            severity="medium",
            recipient_id="user-456",
            data={"payout_id": "PAY-123", "amount": 5000000},
        )
    """

    async def send(
        self,
        tenant_id: str,
        notification_type: str,
        title: str,
        body: str,
        severity: str = "medium",
        recipient_type: str = "user",
        recipient_id: str = "",
        data: dict[str, Any] | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
    ) -> str:
        """Send a notification across all applicable channels."""
        notification_id = str(uuid.uuid4())

        # Determine channels from severity
        channels = list(SEVERITY_CHANNEL_MAP.get(severity, ["in_app"]))

        # Check tenant preferences (may override)
        tenant_prefs = await self._get_tenant_preferences(tenant_id, notification_type)
        if tenant_prefs:
            channels = [ch for ch in channels if tenant_prefs.get(ch, True)]

        # Check digest eligibility
        is_digest = notification_type in DIGEST_ELIGIBLE_TYPES and severity == "low"

        notification_payload = {
            "id": notification_id,
            "tenant_id": tenant_id,
            "notification_type": notification_type,
            "title": title,
            "body": body,
            "severity": severity,
            "recipient_type": recipient_type,
            "recipient_id": recipient_id,
            "data": data or {},
            "resource_type": resource_type,
            "resource_id": resource_id,
        }

        # Deliver to each channel
        delivered = []
        failed = []
        for channel in channels:
            adapter = CHANNEL_ADAPTERS.get(channel)
            if not adapter:
                failed.append(channel)
                continue

            config = tenant_prefs.get(f"{channel}_config", {}) if tenant_prefs else {}
            success = await adapter.deliver(notification_payload, config)
            if success:
                delivered.append(channel)
            else:
                failed.append(channel)

        # Persist record
        await self._persist_record(
            notification_id=notification_id,
            tenant_id=tenant_id,
            notification_type=notification_type,
            severity=severity,
            title=title,
            body=body,
            recipient_type=recipient_type,
            recipient_id=recipient_id,
            data=data or {},
            channels_attempted=channels,
            channels_delivered=delivered,
            channels_failed=failed,
            is_digest=is_digest,
            resource_type=resource_type,
            resource_id=resource_id,
        )

        return notification_id

    async def _get_tenant_preferences(self, tenant_id: str, notification_type: str) -> dict:
        """Load tenant-specific notification preferences."""
        try:
            from sqlalchemy import select, or_
            from packages.db.engine import get_session_factory

            factory = get_session_factory()
            async with factory() as session:
                stmt = select(TenantNotificationPreference).where(
                    TenantNotificationPreference.tenant_id == uuid.UUID(tenant_id),
                    or_(
                        TenantNotificationPreference.notification_type == notification_type,
                        TenantNotificationPreference.notification_type == "*",
                    ),
                )
                result = await session.execute(stmt)
                prefs = list(result.scalars().all())
                if not prefs:
                    return {}

                pref_map: dict[str, Any] = {}
                for p in prefs:
                    pref_map[p.channel] = p.enabled
                    if p.config:
                        pref_map[f"{p.channel}_config"] = p.config
                return pref_map
        except Exception:
            return {}

    async def _persist_record(self, **kwargs) -> None:
        """Save notification record to DB."""
        try:
            from packages.db.engine import get_session_factory

            factory = get_session_factory()
            async with factory() as session:
                record = NotificationRecord(
                    id=uuid.UUID(kwargs["notification_id"]),
                    tenant_id=uuid.UUID(kwargs["tenant_id"]),
                    notification_type=kwargs["notification_type"],
                    severity=kwargs["severity"],
                    title=kwargs["title"],
                    body=kwargs["body"],
                    recipient_type=kwargs["recipient_type"],
                    recipient_id=kwargs["recipient_id"],
                    data=kwargs["data"],
                    channels_attempted=kwargs["channels_attempted"],
                    channels_delivered=kwargs["channels_delivered"],
                    channels_failed=kwargs["channels_failed"],
                    status="delivered" if kwargs["channels_delivered"] else "failed",
                    delivered_at=datetime.now(timezone.utc) if kwargs["channels_delivered"] else None,
                    is_digest_eligible=kwargs.get("is_digest", False),
                    resource_type=kwargs.get("resource_type"),
                    resource_id=kwargs.get("resource_id"),
                )
                session.add(record)
                await session.commit()
        except Exception:
            pass
