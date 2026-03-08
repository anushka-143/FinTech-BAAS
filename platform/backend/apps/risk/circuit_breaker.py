"""Defensive AI Circuit Breakers — reversible protective actions.

The audit identified a gap: the doctrine defines what AI CANNOT do
(move money, mutate ledger, bypass controls) but missed what AI CAN do
for reversible, defensive actions during detected attacks.

This service allows the AI to trigger protective circuit breakers
that are:
  - Reversible (human can override/extend)
  - Logged to audit trail
  - Auto-expiring (default 1 hour TTL)
  - Limited to defensive actions only

Example: If AI detects a credential stuffing attack at 3 AM, it can
pause that tenant's API keys until a human reviews.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import StrEnum
from typing import Any


class BreakerAction(StrEnum):
    PAUSE_WEBHOOKS = "pause_webhooks"
    RATE_LIMIT_TENANT = "rate_limit_tenant"
    FLAG_FOR_REVIEW = "flag_for_review"
    FREEZE_API_KEY = "freeze_api_key"
    PAUSE_PAYOUTS = "pause_payouts"


@dataclass
class CircuitBreakerEvent:
    """A triggered circuit breaker action."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    action: str = ""
    tenant_id: str = ""
    entity_type: str = ""
    entity_id: str = ""
    reason: str = ""
    triggered_by: str = "ai_engine"
    triggered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime | None = None
    is_active: bool = True
    resolved_by: str | None = None
    resolved_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


# In-memory store for sandbox — production uses Redis + DB
_active_breakers: dict[str, CircuitBreakerEvent] = {}

DEFAULT_TTL_MINUTES = 60


class CircuitBreakerService:
    """Manages defensive circuit breakers that AI can trigger.

    Allowed actions (all reversible):
      1. pause_webhooks — stops webhook delivery for a tenant
      2. rate_limit_tenant — reduces API rate limit
      3. flag_for_review — marks entity for human review
      4. freeze_api_key — disables an API key (human must re-enable)
      5. pause_payouts — temporarily halts payout dispatch

    All actions:
      - Are logged to audit trail
      - Auto-expire after TTL (default 1 hour)
      - Can be manually resolved by a human
    """

    def trigger(
        self,
        *,
        action: str,
        tenant_id: str,
        reason: str,
        entity_type: str = "",
        entity_id: str = "",
        ttl_minutes: int = DEFAULT_TTL_MINUTES,
        metadata: dict | None = None,
    ) -> CircuitBreakerEvent:
        """Trigger a defensive circuit breaker.

        Returns the event for audit logging.
        """
        if action not in BreakerAction.__members__.values():
            raise ValueError(f"Unknown breaker action: {action}. Allowed: {list(BreakerAction)}")

        now = datetime.now(timezone.utc)
        event = CircuitBreakerEvent(
            action=action,
            tenant_id=tenant_id,
            entity_type=entity_type,
            entity_id=entity_id,
            reason=reason,
            triggered_at=now,
            expires_at=now + timedelta(minutes=ttl_minutes),
            metadata=metadata or {},
        )

        _active_breakers[event.id] = event
        return event

    def resolve(
        self,
        breaker_id: str,
        resolved_by: str = "ops_user",
    ) -> CircuitBreakerEvent | None:
        """Manually resolve / override a circuit breaker."""
        event = _active_breakers.get(breaker_id)
        if event is None:
            return None

        event.is_active = False
        event.resolved_by = resolved_by
        event.resolved_at = datetime.now(timezone.utc)
        return event

    def get_active(self, tenant_id: str | None = None) -> list[CircuitBreakerEvent]:
        """List active circuit breakers, optionally filtered by tenant."""
        now = datetime.now(timezone.utc)
        active = []
        for event in _active_breakers.values():
            if not event.is_active:
                continue
            # Auto-expire
            if event.expires_at and event.expires_at < now:
                event.is_active = False
                continue
            if tenant_id and event.tenant_id != tenant_id:
                continue
            active.append(event)
        return active

    def is_breaker_active(self, action: str, tenant_id: str) -> bool:
        """Check if a specific breaker type is active for a tenant."""
        for event in self.get_active(tenant_id):
            if event.action == action:
                return True
        return False

    def cleanup_expired(self) -> int:
        """Remove expired breakers from memory. Returns count removed."""
        now = datetime.now(timezone.utc)
        expired_ids = [
            eid for eid, e in _active_breakers.items()
            if e.expires_at and e.expires_at < now
        ]
        for eid in expired_ids:
            del _active_breakers[eid]
        return len(expired_ids)
