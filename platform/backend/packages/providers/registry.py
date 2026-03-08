"""Provider Abstraction Framework — capability matrix, health, failover.

Formalizes provider adapters for:
  - Payouts (UPI, IMPS, NEFT, RTGS)
  - KYC (identity verification, OCR)
  - Collections (virtual accounts, payment links)
  - Sanctions (UAPA, OFAC)
  - Notifications (email, SMS, push)

Each provider has: capability matrix, health state, retry policy,
normalization layer, contract tests, and failover semantics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any


class ProviderDomain(StrEnum):
    PAYOUTS = "payouts"
    KYC = "kyc"
    COLLECTIONS = "collections"
    SANCTIONS = "sanctions"
    NOTIFICATIONS = "notifications"


class ProviderHealth(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    MAINTENANCE = "maintenance"


@dataclass
class RetryPolicy:
    """Retry configuration for a provider."""
    max_retries: int = 3
    initial_delay_ms: int = 1000
    backoff_multiplier: float = 2.0
    max_delay_ms: int = 30000
    retry_on_status_codes: list[int] = field(default_factory=lambda: [429, 500, 502, 503, 504])


@dataclass
class ProviderCapability:
    """What a provider can do."""
    rails: list[str] = field(default_factory=list)   # For payouts: ["upi", "imps"]
    features: list[str] = field(default_factory=list)  # ["instant", "scheduled", "bulk"]
    max_amount_paise: int = 0
    min_amount_paise: int = 0
    supported_currencies: list[str] = field(default_factory=lambda: ["INR"])
    api_version: str = "1.0"


@dataclass
class ProviderConfig:
    """Full configuration for a registered provider."""
    name: str
    domain: ProviderDomain
    base_url: str
    api_key_env: str  # Environment variable name for API key
    capabilities: ProviderCapability
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    health: ProviderHealth = ProviderHealth.HEALTHY
    is_primary: bool = False
    is_sandbox: bool = False
    priority: int = 100  # Lower = preferred
    last_health_check: datetime | None = None
    success_rate_7d: float = 1.0
    avg_latency_ms: float = 0.0


# ─── Provider Registry ───

class ProviderRegistry:
    """Central registry of all external providers.

    Handles:
      - Registration and discovery
      - Health tracking
      - Failover decisions
      - Capability matching
    """

    def __init__(self):
        self._providers: dict[str, ProviderConfig] = {}

    def register(self, config: ProviderConfig) -> None:
        self._providers[config.name] = config

    def get(self, name: str) -> ProviderConfig | None:
        return self._providers.get(name)

    def list_by_domain(self, domain: ProviderDomain) -> list[ProviderConfig]:
        """List providers for a domain, sorted by priority."""
        return sorted(
            [p for p in self._providers.values() if p.domain == domain],
            key=lambda p: p.priority,
        )

    def get_primary(self, domain: ProviderDomain) -> ProviderConfig | None:
        """Get the primary provider for a domain."""
        providers = self.list_by_domain(domain)
        primary = [p for p in providers if p.is_primary and p.health == ProviderHealth.HEALTHY]
        return primary[0] if primary else (providers[0] if providers else None)

    def get_failover(self, domain: ProviderDomain, exclude: str) -> ProviderConfig | None:
        """Get failover provider (next healthy provider, excluding the failed one)."""
        providers = self.list_by_domain(domain)
        candidates = [
            p for p in providers
            if p.name != exclude and p.health in (ProviderHealth.HEALTHY, ProviderHealth.DEGRADED)
        ]
        return candidates[0] if candidates else None

    def find_for_capability(self, domain: ProviderDomain, rail: str) -> list[ProviderConfig]:
        """Find providers that support a specific rail/capability."""
        return [
            p for p in self.list_by_domain(domain)
            if rail in p.capabilities.rails and p.health == ProviderHealth.HEALTHY
        ]

    def update_health(self, name: str, health: ProviderHealth) -> None:
        if name in self._providers:
            self._providers[name].health = health
            self._providers[name].last_health_check = datetime.now(timezone.utc)

    def update_metrics(self, name: str, success_rate: float, avg_latency_ms: float) -> None:
        if name in self._providers:
            self._providers[name].success_rate_7d = success_rate
            self._providers[name].avg_latency_ms = avg_latency_ms

    def get_status(self) -> list[dict]:
        """Get health status of all providers."""
        return [
            {
                "name": p.name,
                "domain": p.domain,
                "health": p.health,
                "is_primary": p.is_primary,
                "success_rate_7d": p.success_rate_7d,
                "avg_latency_ms": p.avg_latency_ms,
                "rails": p.capabilities.rails,
            }
            for p in self._providers.values()
        ]


# ─── Default providers ───

def create_default_registry() -> ProviderRegistry:
    """Create registry with default sandbox providers."""
    registry = ProviderRegistry()

    registry.register(ProviderConfig(
        name="sandbox_payouts", domain=ProviderDomain.PAYOUTS,
        base_url="http://localhost:8000/sandbox/payouts",
        api_key_env="SANDBOX_API_KEY",
        capabilities=ProviderCapability(
            rails=["upi", "imps", "neft", "rtgs"],
            features=["instant", "scheduled"],
            max_amount_paise=50_00_000_00,
        ),
        is_primary=True, is_sandbox=True,
    ))

    registry.register(ProviderConfig(
        name="sandbox_kyc", domain=ProviderDomain.KYC,
        base_url="http://localhost:8000/sandbox/kyc",
        api_key_env="SANDBOX_API_KEY",
        capabilities=ProviderCapability(
            features=["aadhaar_verify", "pan_verify", "face_match"],
        ),
        is_primary=True, is_sandbox=True,
    ))

    return registry


# Singleton
_registry: ProviderRegistry | None = None


def get_provider_registry() -> ProviderRegistry:
    global _registry
    if _registry is None:
        _registry = create_default_registry()
    return _registry
