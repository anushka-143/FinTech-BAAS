"""RBAC + ABAC authorization engine.

RBAC: role-based checks (viewer, ops_analyst, finance_operator, risk_reviewer, tenant_admin, platform_admin)
ABAC: attribute-based policies (same tenant, amount threshold, PII clearance, maker-checker)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from packages.core.context import TenantContext
from packages.core.errors import AuthorizationError


class Role(StrEnum):
    VIEWER = "viewer"
    OPS_ANALYST = "ops_analyst"
    FINANCE_OPERATOR = "finance_operator"
    RISK_REVIEWER = "risk_reviewer"
    TENANT_ADMIN = "tenant_admin"
    PLATFORM_ADMIN = "platform_admin"


class Permission(StrEnum):
    # Payouts
    PAYOUT_CREATE = "payout:create"
    PAYOUT_READ = "payout:read"
    PAYOUT_APPROVE = "payout:approve"
    PAYOUT_RETRY = "payout:retry"
    # Collections
    VA_CREATE = "va:create"
    VA_READ = "va:read"
    COLLECTION_READ = "collection:read"
    # KYC
    KYC_CREATE = "kyc:create"
    KYC_READ = "kyc:read"
    KYC_DECIDE = "kyc:decide"
    # Ledger
    LEDGER_READ = "ledger:read"
    LEDGER_JOURNAL_CREATE = "ledger:journal:create"
    # Risk
    RISK_READ = "risk:read"
    RISK_INVESTIGATE = "risk:investigate"
    # Recon
    RECON_READ = "recon:read"
    RECON_RUN = "recon:run"
    # Webhooks
    WEBHOOK_MANAGE = "webhook:manage"
    WEBHOOK_REPLAY = "webhook:replay"
    # Audit
    AUDIT_READ = "audit:read"
    AUDIT_EXPORT = "audit:export"
    # Admin
    TENANT_MANAGE = "tenant:manage"
    API_KEY_MANAGE = "api_key:manage"
    USER_MANAGE = "user:manage"
    # AI
    AI_COPILOT = "ai:copilot"


# Default permission sets per role
ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.VIEWER: frozenset({
        Permission.PAYOUT_READ,
        Permission.VA_READ,
        Permission.COLLECTION_READ,
        Permission.KYC_READ,
        Permission.LEDGER_READ,
        Permission.RISK_READ,
        Permission.RECON_READ,
        Permission.AUDIT_READ,
    }),
    Role.OPS_ANALYST: frozenset({
        Permission.PAYOUT_READ,
        Permission.PAYOUT_RETRY,
        Permission.VA_READ,
        Permission.COLLECTION_READ,
        Permission.KYC_READ,
        Permission.KYC_CREATE,
        Permission.LEDGER_READ,
        Permission.RISK_READ,
        Permission.RECON_READ,
        Permission.RECON_RUN,
        Permission.AUDIT_READ,
        Permission.AI_COPILOT,
    }),
    Role.FINANCE_OPERATOR: frozenset({
        Permission.PAYOUT_CREATE,
        Permission.PAYOUT_READ,
        Permission.PAYOUT_APPROVE,
        Permission.PAYOUT_RETRY,
        Permission.VA_CREATE,
        Permission.VA_READ,
        Permission.COLLECTION_READ,
        Permission.LEDGER_READ,
        Permission.LEDGER_JOURNAL_CREATE,
        Permission.RECON_READ,
        Permission.RECON_RUN,
        Permission.AUDIT_READ,
        Permission.AI_COPILOT,
    }),
    Role.RISK_REVIEWER: frozenset({
        Permission.PAYOUT_READ,
        Permission.KYC_READ,
        Permission.KYC_DECIDE,
        Permission.RISK_READ,
        Permission.RISK_INVESTIGATE,
        Permission.AUDIT_READ,
        Permission.AI_COPILOT,
    }),
    Role.TENANT_ADMIN: frozenset({
        # gets everything except platform-level
        p for p in Permission if not p.startswith("tenant:manage")
    }),
    Role.PLATFORM_ADMIN: frozenset(Permission),
}


def get_permissions_for_roles(roles: frozenset[str]) -> frozenset[Permission]:
    """Resolve all permissions from a set of role names."""
    perms: set[Permission] = set()
    for role_name in roles:
        try:
            role = Role(role_name)
        except ValueError:
            continue
        perms.update(ROLE_PERMISSIONS.get(role, frozenset()))
    return frozenset(perms)


@dataclass(frozen=True, slots=True)
class ABACPolicy:
    """Attribute-based policy check."""

    name: str
    description: str

    def evaluate(self, ctx: TenantContext, resource: dict[str, Any]) -> bool:
        raise NotImplementedError


class SameTenantPolicy(ABACPolicy):
    """Ensures the requesting user belongs to the same tenant as the resource."""

    def evaluate(self, ctx: TenantContext, resource: dict[str, Any]) -> bool:
        resource_tenant = resource.get("tenant_id")
        if resource_tenant is None:
            return True
        return str(ctx.tenant_id) == str(resource_tenant)


class AmountThresholdPolicy(ABACPolicy):
    """Blocks operations over a certain amount without approval."""

    def __init__(self, max_amount_minor: int) -> None:
        super().__init__(
            name="amount_threshold",
            description=f"Requires approval for amounts over {max_amount_minor}",
        )
        self.max_amount_minor = max_amount_minor

    def evaluate(self, ctx: TenantContext, resource: dict[str, Any]) -> bool:
        amount = resource.get("amount", 0)
        if amount > self.max_amount_minor:
            return ctx.has_permission(Permission.PAYOUT_APPROVE)
        return True


class MakerCheckerPolicy(ABACPolicy):
    """Prevents the same user from both creating and approving a resource."""

    def evaluate(self, ctx: TenantContext, resource: dict[str, Any]) -> bool:
        created_by = resource.get("created_by")
        if created_by and str(ctx.user_id) == str(created_by):
            return False
        return True


def require_permission(ctx: TenantContext, permission: Permission) -> None:
    """Raise AuthorizationError if the tenant context lacks the required permission."""
    all_perms = get_permissions_for_roles(ctx.roles) | ctx.permissions
    if permission not in all_perms:
        raise AuthorizationError(f"Missing permission: {permission}")


def require_policies(
    ctx: TenantContext,
    resource: dict[str, Any],
    policies: list[ABACPolicy],
) -> None:
    """Evaluate all ABAC policies and raise on first failure."""
    for policy in policies:
        if not policy.evaluate(ctx, resource):
            raise AuthorizationError(f"Policy check failed: {policy.name}")
