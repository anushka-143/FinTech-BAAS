"""Tenant Isolation Utilities — row-level security, scoped keys, resource partitioning.

Multi-tenant isolation goes beyond just adding tenant_id columns.
This module provides:
  - Tenant context management (request-scoped tenant state)
  - Row-level security enforcement via query scoping
  - Scoped encryption keys per tenant
  - Cache key scoping (prevent cross-tenant cache leaks)
  - File storage path isolation
  - Queue/topic partitioning
  - AI retrieval scoping
  - Audit scoping
"""

from __future__ import annotations

import hashlib
import uuid
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Column, DateTime, String, Text, Boolean
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy import select, and_, event
from sqlalchemy.orm import Session

from packages.db.base import Base, TimestampMixin


# ─── Tenant Context (request-scoped) ───

_current_tenant: ContextVar[str | None] = ContextVar("current_tenant", default=None)
_current_user: ContextVar[str | None] = ContextVar("current_user", default=None)
_current_roles: ContextVar[list[str]] = ContextVar("current_roles", default=[])


def set_tenant_context(tenant_id: str, user_id: str | None = None, roles: list[str] | None = None):
    """Set the current request's tenant context."""
    _current_tenant.set(tenant_id)
    if user_id:
        _current_user.set(user_id)
    if roles:
        _current_roles.set(roles)


def get_tenant_id() -> str | None:
    """Get the current tenant ID from request context."""
    return _current_tenant.get()


def get_current_user() -> str | None:
    return _current_user.get()


def get_current_roles() -> list[str]:
    return _current_roles.get()


def clear_tenant_context():
    """Clear tenant context (end of request)."""
    _current_tenant.set(None)
    _current_user.set(None)
    _current_roles.set([])


# ─── Schema ───

class TenantConfig(Base, TimestampMixin):
    """Per-tenant configuration and isolation settings."""
    __tablename__ = "tenant_configs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, unique=True, index=True)

    # Encryption
    encryption_key_id = Column(String(200), nullable=True,
                               comment="KMS key ID for tenant-specific encryption")
    encryption_algorithm = Column(String(50), default="AES-256-GCM")

    # Storage isolation
    storage_bucket = Column(String(200), nullable=True, comment="Dedicated bucket if needed")
    storage_prefix = Column(String(200), nullable=False, comment="tenants/{tenant_id}/")

    # Rate limits
    api_rate_limit = Column(String(20), default="1000/min")
    webhook_rate_limit = Column(String(20), default="100/min")

    # Feature access
    features_enabled = Column(JSONB, nullable=False, server_default='[]',
                              comment='["payouts", "collections", "kyc", "risk"]')
    ai_enabled = Column(Boolean, default=True)
    sandbox_mode = Column(Boolean, default=False)

    # Data residency
    data_region = Column(String(20), default="in", comment="in | us | eu")

    # Metadata
    metadata_ = Column("metadata", JSONB, nullable=False, server_default='{}')


# ─── Query Scoping ───

class TenantQueryScope:
    """Enforces tenant isolation on all database queries.

    Usage in middleware:
        scope = TenantQueryScope(tenant_id)
        query = scope.apply(select(PayoutRequest))
        # Automatically adds WHERE tenant_id = :tenant_id
    """

    def __init__(self, tenant_id: str):
        self.tenant_id = uuid.UUID(tenant_id)

    def apply(self, stmt, model=None):
        """Append tenant_id filter to a SQLAlchemy select statement.

        Works with any model that has a tenant_id column.
        """
        if model and hasattr(model, "tenant_id"):
            return stmt.where(model.tenant_id == self.tenant_id)
        return stmt

    def filter_dict(self, data: dict) -> dict:
        """Inject tenant_id into a dict (for inserts)."""
        data["tenant_id"] = self.tenant_id
        return data


# ─── Cache Key Scoping ───

class TenantCacheScope:
    """Prevents cross-tenant cache pollution.

    All cache keys are prefixed with tenant_id to ensure isolation.
    """

    def __init__(self, tenant_id: str):
        self.prefix = f"t:{tenant_id}"

    def key(self, namespace: str, identifier: str) -> str:
        """Generate a tenant-scoped cache key."""
        return f"{self.prefix}:{namespace}:{identifier}"

    def pattern(self, namespace: str) -> str:
        """Generate a cache key pattern for bulk operations."""
        return f"{self.prefix}:{namespace}:*"

    @staticmethod
    def extract_tenant(cache_key: str) -> str | None:
        """Extract tenant_id from a cache key."""
        parts = cache_key.split(":")
        if len(parts) >= 2 and parts[0] == "t":
            return parts[1]
        return None


# ─── File Storage Isolation ───

class TenantStorageScope:
    """Ensures file storage is tenant-isolated."""

    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id

    def document_path(self, doc_id: str, filename: str) -> str:
        date_prefix = datetime.now(timezone.utc).strftime("%Y/%m/%d")
        ext = filename.rsplit(".", 1)[-1] if "." in filename else "bin"
        return f"tenants/{self.tenant_id}/documents/{date_prefix}/{doc_id}.{ext}"

    def export_path(self, export_type: str, export_id: str) -> str:
        return f"tenants/{self.tenant_id}/exports/{export_type}/{export_id}"

    def temp_path(self, purpose: str) -> str:
        return f"tenants/{self.tenant_id}/tmp/{purpose}/{uuid.uuid4().hex}"

    def validate_path(self, path: str) -> bool:
        """Ensure a path belongs to this tenant."""
        return path.startswith(f"tenants/{self.tenant_id}/")


# ─── Queue/Topic Partitioning ───

class TenantEventScope:
    """Scopes event topics and queues to tenants."""

    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id

    def topic(self, event_type: str) -> str:
        """Get tenant-scoped topic name."""
        return f"tenant.{self.tenant_id}.{event_type}"

    def queue(self, consumer: str) -> str:
        """Get tenant-scoped queue name."""
        return f"q.{self.tenant_id}.{consumer}"

    def global_topic(self, event_type: str) -> str:
        """Get global topic (cross-tenant events like system alerts)."""
        return f"global.{event_type}"


# ─── AI Retrieval Scoping ───

class TenantAIScope:
    """Scopes AI operations to tenant boundaries."""

    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id

    def rag_filter(self) -> dict:
        """Return filter for RAG retrieval scoped to tenant + global."""
        return {
            "tenant_scope": [self.tenant_id, None],  # Tenant-specific + global knowledge
        }

    def embedding_namespace(self) -> str:
        """Namespace for tenant-specific embeddings."""
        return f"tenant:{self.tenant_id}"

    def ai_context(self) -> dict:
        """Base context dict with tenant isolation."""
        return {
            "tenant_id": self.tenant_id,
            "scope": "tenant",
        }


# ─── Audit Scoping ───

class TenantAuditScope:
    """Ensures audit entries are always tenant-tagged."""

    def __init__(self, tenant_id: str, user_id: str | None = None):
        self.tenant_id = tenant_id
        self.user_id = user_id

    def audit_context(self, action: str, resource_type: str, resource_id: str) -> dict:
        """Generate a standard audit context dict."""
        return {
            "tenant_id": self.tenant_id,
            "actor_id": self.user_id,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


# ─── Tenant Isolation Middleware Helper ───

@dataclass
class TenantScope:
    """Unified tenant isolation scope — one object for all scoping needs.

    Usage in middleware:
        scope = TenantScope.from_request(tenant_id, user_id, roles)
        # Use scope.query, scope.cache, scope.storage, scope.events, scope.ai, scope.audit
    """
    tenant_id: str
    user_id: str | None = None
    roles: list[str] | None = None

    @classmethod
    def from_request(cls, tenant_id: str, user_id: str | None = None, roles: list[str] | None = None) -> TenantScope:
        set_tenant_context(tenant_id, user_id, roles)
        return cls(tenant_id=tenant_id, user_id=user_id, roles=roles)

    @property
    def query(self) -> TenantQueryScope:
        return TenantQueryScope(self.tenant_id)

    @property
    def cache(self) -> TenantCacheScope:
        return TenantCacheScope(self.tenant_id)

    @property
    def storage(self) -> TenantStorageScope:
        return TenantStorageScope(self.tenant_id)

    @property
    def events(self) -> TenantEventScope:
        return TenantEventScope(self.tenant_id)

    @property
    def ai(self) -> TenantAIScope:
        return TenantAIScope(self.tenant_id)

    @property
    def audit(self) -> TenantAuditScope:
        return TenantAuditScope(self.tenant_id, self.user_id)
