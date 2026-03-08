"""Abstract provider adapter interfaces.

Each adapter normalizes provider-specific behavior into internal canonical models.
Concrete adapters must never leak provider-specific types into the core domain.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class ProviderPayoutRequest:
    beneficiary_account: str
    beneficiary_ifsc: str | None
    beneficiary_vpa: str | None
    beneficiary_name: str
    amount_minor: int
    currency: str
    purpose: str
    narration: str
    rail: str
    reference_id: str


@dataclass(frozen=True, slots=True)
class ProviderPayoutResponse:
    provider_reference: str
    status: str  # accepted | rejected | pending | success | failed
    raw_status: str
    message: str
    raw_response: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ProviderPayoutStatus:
    provider_reference: str
    status: str
    raw_status: str
    utr: str | None = None
    failure_code: str | None = None
    failure_reason: str | None = None
    completed_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class ProviderVARequest:
    name: str
    bank_code: str
    purpose: str | None
    is_permanent: bool
    expected_amount: int | None


@dataclass(frozen=True, slots=True)
class ProviderVAResponse:
    va_number: str
    ifsc: str
    bank_code: str
    status: str
    raw_response: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ProviderKYCVerifyRequest:
    document_type: str
    document_number: str
    name: str | None
    dob: str | None
    additional_params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ProviderKYCVerifyResponse:
    is_valid: bool
    matched_name: str | None
    details: dict[str, Any] = field(default_factory=dict)
    raw_response: dict[str, Any] = field(default_factory=dict)


class PayoutProviderAdapter(ABC):
    """Abstract adapter for payout rail providers."""

    @abstractmethod
    async def initiate_payout(self, request: ProviderPayoutRequest) -> ProviderPayoutResponse:
        ...

    @abstractmethod
    async def get_payout_status(self, provider_reference: str) -> ProviderPayoutStatus:
        ...


class VirtualAccountProviderAdapter(ABC):
    """Abstract adapter for virtual account providers."""

    @abstractmethod
    async def create_virtual_account(self, request: ProviderVARequest) -> ProviderVAResponse:
        ...

    @abstractmethod
    async def close_virtual_account(self, va_number: str) -> bool:
        ...


class KYCProviderAdapter(ABC):
    """Abstract adapter for KYC verification providers."""

    @abstractmethod
    async def verify_document(
        self, request: ProviderKYCVerifyRequest
    ) -> ProviderKYCVerifyResponse:
        ...
