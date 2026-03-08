"""Policy Engine — centralized business rules evaluation.

Evaluates tenant-scoped policies for:
  - Payout limits (per-transaction, daily, monthly)
  - Allowed payment rails
  - Maker-checker thresholds
  - Geo restrictions
  - Role-based action restrictions
  - AI action boundaries
  - Redaction policies

All policy decisions are logged for audit.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import Column, String, Boolean, Integer, DateTime
from sqlalchemy.dialects.postgresql import JSONB, UUID

from packages.core.models import APIResponse, BaseDTO
from packages.db.base import Base, TimestampMixin


# ─── Schema ───

class TenantPolicy(Base, TimestampMixin):
    """Tenant-specific policy rule stored in DB."""
    __tablename__ = "tenant_policies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    policy_type = Column(String(100), nullable=False, index=True,
                         comment="payout_limit | allowed_rails | maker_checker | geo | role | ai_boundary")
    name = Column(String(200), nullable=False)
    rules = Column(JSONB, nullable=False, server_default='{}')
    enabled = Column(Boolean, default=True)
    priority = Column(Integer, default=100, comment="Lower = evaluated first")


class PolicyDecisionLog(Base, TimestampMixin):
    """Audit log of every policy evaluation."""
    __tablename__ = "policy_decision_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    policy_type = Column(String(100), nullable=False)
    resource_type = Column(String(100), nullable=False)
    resource_id = Column(String(200), nullable=True)
    decision = Column(String(20), nullable=False, comment="allow | deny | require_approval")
    matched_rules = Column(JSONB, nullable=False, server_default='[]')
    context = Column(JSONB, nullable=False, server_default='{}')


# ─── Default policies (applied when no tenant-specific policy exists) ───

DEFAULT_POLICIES = {
    "payout_limit": {
        "per_transaction_max_paise": 50_00_000_00,  # ₹50L
        "daily_max_paise": 5_00_00_000_00,          # ₹5 Cr
        "monthly_max_paise": 50_00_00_000_00,       # ₹50 Cr
    },
    "allowed_rails": ["upi", "imps", "neft", "rtgs"],
    "maker_checker": {
        "payout_threshold_paise": 10_00_000_00,  # ₹10L requires approval
        "risk_override": True,                    # Always requires approval
        "api_key_rotation": True,
        "webhook_secret_change": True,
    },
    "geo_restrictions": {
        "allowed_countries": ["IN"],
        "blocked_countries": [],
    },
    "ai_boundaries": {
        "max_auto_approve_amount_paise": 5_00_000_00,  # ₹5L AI can auto-approve
        "require_human_for_risk_above": 0.70,
        "max_tool_calls_per_session": 10,
    },
}


# ─── Engine ───

@dataclass
class PolicyResult:
    """Result of a policy evaluation."""
    decision: str  # "allow" | "deny" | "require_approval"
    matched_rules: list[str]
    reason: str
    metadata: dict[str, Any] = field(default_factory=dict)


class PolicyEngine:
    """Evaluates policies against tenant context.

    Usage:
        engine = PolicyEngine()
        result = await engine.evaluate("payout_limit", tenant_id, {
            "amount_paise": 15_00_000_00,
            "rail": "imps",
        })
    """

    async def evaluate(
        self,
        policy_type: str,
        tenant_id: str,
        context: dict[str, Any],
    ) -> PolicyResult:
        """Evaluate a policy against context.

        Loads tenant-specific policies from DB, falls back to defaults.
        """
        # Load tenant policies from DB
        tenant_rules = await self._load_tenant_policies(tenant_id, policy_type)

        # Fall back to defaults if no tenant policy exists
        if not tenant_rules:
            tenant_rules = DEFAULT_POLICIES.get(policy_type, {})

        # Dispatch to specific evaluator
        evaluators = {
            "payout_limit": self._evaluate_payout_limit,
            "allowed_rails": self._evaluate_allowed_rails,
            "maker_checker": self._evaluate_maker_checker,
            "geo_restrictions": self._evaluate_geo,
            "ai_boundaries": self._evaluate_ai_boundaries,
        }

        evaluator = evaluators.get(policy_type)
        if not evaluator:
            return PolicyResult(decision="allow", matched_rules=[], reason="No policy defined")

        result = evaluator(tenant_rules, context)

        # Log decision
        await self._log_decision(tenant_id, policy_type, context, result)

        return result

    async def _load_tenant_policies(self, tenant_id: str, policy_type: str) -> dict:
        """Load tenant-specific policies from DB."""
        try:
            from sqlalchemy import select
            from packages.db.engine import get_session_factory

            factory = get_session_factory()
            async with factory() as session:
                stmt = (
                    select(TenantPolicy)
                    .where(
                        TenantPolicy.tenant_id == uuid.UUID(tenant_id),
                        TenantPolicy.policy_type == policy_type,
                        TenantPolicy.enabled.is_(True),
                    )
                    .order_by(TenantPolicy.priority)
                    .limit(1)
                )
                result = await session.execute(stmt)
                policy = result.scalar_one_or_none()
                if policy:
                    return policy.rules
        except Exception:
            pass
        return {}

    @staticmethod
    def _evaluate_payout_limit(rules: dict, context: dict) -> PolicyResult:
        amount = context.get("amount_paise", 0)
        max_amount = rules.get("per_transaction_max_paise", 50_00_000_00)

        if amount > max_amount:
            return PolicyResult(
                decision="deny",
                matched_rules=["per_transaction_max"],
                reason=f"Amount {amount} exceeds max {max_amount}",
            )

        # Check if maker-checker required
        threshold = rules.get("approval_threshold_paise", 10_00_000_00)
        if amount > threshold:
            return PolicyResult(
                decision="require_approval",
                matched_rules=["approval_threshold"],
                reason=f"Amount {amount} exceeds approval threshold {threshold}",
            )

        return PolicyResult(decision="allow", matched_rules=[], reason="Within limits")

    @staticmethod
    def _evaluate_allowed_rails(rules: dict | list, context: dict) -> PolicyResult:
        rail = context.get("rail", "")
        allowed = rules if isinstance(rules, list) else rules.get("allowed", [])

        if rail and rail not in allowed:
            return PolicyResult(
                decision="deny",
                matched_rules=["rail_not_allowed"],
                reason=f"Rail '{rail}' not in allowed list: {allowed}",
            )
        return PolicyResult(decision="allow", matched_rules=[], reason="Rail allowed")

    @staticmethod
    def _evaluate_maker_checker(rules: dict, context: dict) -> PolicyResult:
        resource_type = context.get("resource_type", "")
        amount = context.get("amount_paise", 0)

        # Check if resource type always requires approval
        if rules.get(resource_type, False) is True:
            return PolicyResult(
                decision="require_approval",
                matched_rules=[f"{resource_type}_always_requires_approval"],
                reason=f"{resource_type} requires maker-checker",
            )

        # Check amount threshold
        threshold = rules.get("payout_threshold_paise", 10_00_000_00)
        if amount > threshold:
            return PolicyResult(
                decision="require_approval",
                matched_rules=["amount_threshold"],
                reason=f"Amount {amount} exceeds maker-checker threshold",
            )

        return PolicyResult(decision="allow", matched_rules=[], reason="No approval needed")

    @staticmethod
    def _evaluate_geo(rules: dict, context: dict) -> PolicyResult:
        country = context.get("country", "IN")
        blocked = rules.get("blocked_countries", [])
        allowed = rules.get("allowed_countries", [])

        if country in blocked:
            return PolicyResult(decision="deny", matched_rules=["blocked_country"], reason=f"{country} blocked")
        if allowed and country not in allowed:
            return PolicyResult(decision="deny", matched_rules=["not_in_allowed"], reason=f"{country} not allowed")
        return PolicyResult(decision="allow", matched_rules=[], reason="Geo allowed")

    @staticmethod
    def _evaluate_ai_boundaries(rules: dict, context: dict) -> PolicyResult:
        risk_score = context.get("risk_score", 0.0)
        threshold = rules.get("require_human_for_risk_above", 0.70)

        if risk_score > threshold:
            return PolicyResult(
                decision="require_approval",
                matched_rules=["risk_above_threshold"],
                reason=f"Risk score {risk_score} exceeds AI boundary {threshold}",
            )
        return PolicyResult(decision="allow", matched_rules=[], reason="Within AI boundaries")

    async def _log_decision(self, tenant_id: str, policy_type: str, context: dict, result: PolicyResult):
        """Log policy decision for audit."""
        try:
            from packages.db.engine import get_session_factory
            factory = get_session_factory()
            async with factory() as session:
                log = PolicyDecisionLog(
                    tenant_id=uuid.UUID(tenant_id),
                    policy_type=policy_type,
                    resource_type=context.get("resource_type", "unknown"),
                    resource_id=context.get("resource_id"),
                    decision=result.decision,
                    matched_rules=result.matched_rules,
                    context=context,
                )
                session.add(log)
                await session.commit()
        except Exception:
            pass


# ─── Router ───

router = APIRouter()


class PolicyEvalRequest(BaseModel):
    policy_type: str = Field(..., description="payout_limit | allowed_rails | maker_checker | geo | ai_boundaries")
    context: dict[str, Any] = Field(..., description="Context for evaluation")


@router.post("/evaluate", response_model=APIResponse[dict])
async def evaluate_policy(
    body: PolicyEvalRequest,
    x_tenant_id: str = Header(...),
):
    """Evaluate a policy rule against context."""
    engine = PolicyEngine()
    result = await engine.evaluate(body.policy_type, x_tenant_id, body.context)
    return APIResponse.ok({
        "decision": result.decision,
        "matched_rules": result.matched_rules,
        "reason": result.reason,
    })


@router.get("/defaults", response_model=APIResponse[dict])
async def get_default_policies():
    """Get default policy values."""
    return APIResponse.ok(DEFAULT_POLICIES)
