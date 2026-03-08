"""Request-scoped tenant context.

The gateway middleware sets this per-request via a ContextVar.
All downstream services read tenant identity from here — never from the request body.
"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field
from uuid import UUID

_tenant_ctx_var: ContextVar["TenantContext | None"] = ContextVar(
    "tenant_context", default=None
)
_request_id_var: ContextVar[str] = ContextVar("request_id", default="")


@dataclass(frozen=True, slots=True)
class TenantContext:
    """Immutable tenant context resolved from auth token / API key."""

    tenant_id: UUID
    tenant_name: str
    user_id: UUID | None = None
    roles: frozenset[str] = field(default_factory=frozenset)
    permissions: frozenset[str] = field(default_factory=frozenset)
    environment: str = "production"

    def has_role(self, role: str) -> bool:
        return role in self.roles

    def has_permission(self, permission: str) -> bool:
        return permission in self.permissions


def set_tenant_context(ctx: TenantContext) -> None:
    _tenant_ctx_var.set(ctx)


def get_tenant_context() -> TenantContext:
    ctx = _tenant_ctx_var.get()
    if ctx is None:
        raise RuntimeError("Tenant context not set — middleware misconfiguration")
    return ctx


def get_tenant_id() -> UUID:
    return get_tenant_context().tenant_id


def set_request_id(request_id: str) -> None:
    _request_id_var.set(request_id)


def get_request_id() -> str:
    return _request_id_var.get()
