"""Environment & Release Configuration — sandbox/live isolation, feature flags, canary.

Handles:
  - Environment definitions (sandbox, staging, production)
  - Sandbox vs live isolation (separate DB schemas, provider mocking)
  - Test tenant management
  - Feature flag system
  - Canary release path
  - Provider environment mapping (sandbox provider ↔ live provider)
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from sqlalchemy import Column, DateTime, String, Boolean, Integer, Float
from sqlalchemy.dialects.postgresql import JSONB, UUID

from packages.db.base import Base, TimestampMixin


# ─── Schema ───

class FeatureFlag(Base, TimestampMixin):
    """Feature flag for progressive rollout."""
    __tablename__ = "feature_flags"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False, unique=True, index=True)
    description = Column(String(500), nullable=True)
    enabled = Column(Boolean, default=False)
    rollout_percentage = Column(Integer, default=0, comment="0-100, percentage of tenants")
    target_tenants = Column(JSONB, nullable=False, server_default='[]',
                            comment="Specific tenant IDs for targeted rollout")
    environment = Column(String(20), nullable=False, default="all",
                         comment="sandbox | staging | production | all")
    metadata_ = Column("metadata", JSONB, nullable=False, server_default='{}')


class ReleaseRecord(Base, TimestampMixin):
    """Tracks deployment releases for audit."""
    __tablename__ = "release_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    version = Column(String(50), nullable=False)
    environment = Column(String(20), nullable=False)
    release_type = Column(String(20), nullable=False,
                          comment="full | canary | rollback")
    status = Column(String(20), nullable=False, default="deploying",
                    comment="deploying | active | rolled_back | superseded")
    canary_percentage = Column(Integer, nullable=True)
    deployed_at = Column(DateTime(timezone=True), nullable=True)
    deployed_by = Column(String(100), nullable=True)
    changelog = Column(JSONB, nullable=False, server_default='[]')
    health_check_passed = Column(Boolean, nullable=True)


# ─── Environment definitions ───

class Environment(StrEnum):
    SANDBOX = "sandbox"
    STAGING = "staging"
    PRODUCTION = "production"


@dataclass
class EnvironmentConfig:
    """Configuration for a deployment environment."""
    name: Environment
    display_name: str
    is_production: bool = False

    # Database
    db_schema_prefix: str = ""  # e.g. "sandbox_" for schema isolation
    db_connection_pool_size: int = 5

    # Providers
    use_mock_providers: bool = False
    provider_prefix: str = ""  # "sandbox_" prefix for provider selection

    # Rate limits
    api_rate_limit_per_minute: int = 100
    webhook_delivery_enabled: bool = True

    # AI
    ai_enabled: bool = True
    ai_model_override: str | None = None  # Force a specific model in non-prod

    # Data
    synthetic_data_allowed: bool = True
    pii_masking_level: str = "full"  # "none" | "partial" | "full"

    # Monitoring
    detailed_logging: bool = True
    performance_tracing: bool = True


ENVIRONMENTS = {
    Environment.SANDBOX: EnvironmentConfig(
        name=Environment.SANDBOX,
        display_name="Sandbox",
        db_schema_prefix="sandbox_",
        db_connection_pool_size=3,
        use_mock_providers=True,
        provider_prefix="sandbox_",
        api_rate_limit_per_minute=50,
        ai_model_override="gemini-2.5-flash",
        synthetic_data_allowed=True,
        pii_masking_level="full",
        detailed_logging=True,
    ),
    Environment.STAGING: EnvironmentConfig(
        name=Environment.STAGING,
        display_name="Staging",
        db_schema_prefix="staging_",
        db_connection_pool_size=5,
        use_mock_providers=False,
        api_rate_limit_per_minute=200,
        ai_enabled=True,
        synthetic_data_allowed=True,
        pii_masking_level="partial",
        detailed_logging=True,
        performance_tracing=True,
    ),
    Environment.PRODUCTION: EnvironmentConfig(
        name=Environment.PRODUCTION,
        display_name="Production",
        is_production=True,
        db_connection_pool_size=20,
        use_mock_providers=False,
        api_rate_limit_per_minute=1000,
        webhook_delivery_enabled=True,
        ai_enabled=True,
        synthetic_data_allowed=False,
        pii_masking_level="full",
        detailed_logging=False,
        performance_tracing=True,
    ),
}


# ─── Feature Flag Service ───

class FeatureFlagService:
    """Evaluate feature flags for tenants.

    Usage:
        service = FeatureFlagService()
        if await service.is_enabled("new_risk_model", tenant_id="..."):
            # Use new risk model
        else:
            # Use old risk model
    """

    async def is_enabled(
        self, flag_name: str, tenant_id: str | None = None,
        environment: str = "production",
    ) -> bool:
        """Check if a feature flag is enabled for a tenant."""
        try:
            from sqlalchemy import select, or_
            from packages.db.engine import get_session_factory

            factory = get_session_factory()
            async with factory() as session:
                stmt = select(FeatureFlag).where(
                    FeatureFlag.name == flag_name,
                    or_(
                        FeatureFlag.environment == environment,
                        FeatureFlag.environment == "all",
                    ),
                )
                result = await session.execute(stmt)
                flag = result.scalar_one_or_none()

                if not flag:
                    return False

                if not flag.enabled:
                    return False

                # Check specific tenant targeting
                if tenant_id and flag.target_tenants:
                    if tenant_id in flag.target_tenants:
                        return True

                # Check rollout percentage
                if flag.rollout_percentage >= 100:
                    return True
                if flag.rollout_percentage <= 0:
                    return bool(tenant_id and tenant_id in (flag.target_tenants or []))

                # Deterministic hash for consistent rollout
                if tenant_id:
                    import hashlib
                    hash_val = int(hashlib.md5(
                        f"{flag_name}:{tenant_id}".encode()
                    ).hexdigest()[:8], 16)
                    return (hash_val % 100) < flag.rollout_percentage

                return False
        except Exception:
            return False

    async def get_all_flags(self, environment: str = "production") -> list[dict]:
        """Get all feature flags for an environment."""
        try:
            from sqlalchemy import select, or_
            from packages.db.engine import get_session_factory

            factory = get_session_factory()
            async with factory() as session:
                stmt = select(FeatureFlag).where(or_(
                    FeatureFlag.environment == environment,
                    FeatureFlag.environment == "all",
                ))
                result = await session.execute(stmt)
                flags = list(result.scalars().all())

            return [
                {
                    "name": f.name,
                    "enabled": f.enabled,
                    "rollout_percentage": f.rollout_percentage,
                    "environment": f.environment,
                }
                for f in flags
            ]
        except Exception:
            return []


def get_environment_config(env_name: str = "production") -> EnvironmentConfig:
    """Get configuration for the current environment."""
    try:
        return ENVIRONMENTS[Environment(env_name)]
    except (ValueError, KeyError):
        return ENVIRONMENTS[Environment.PRODUCTION]
