"""Shared Pydantic base models and DTOs used across all services."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Generic, TypeVar
from uuid import UUID

import ulid
from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


def generate_ulid() -> str:
    """Generate a ULID string for use as primary key."""
    return str(ulid.new())


class Environment(str, enum.Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class BaseDTO(BaseModel):
    """Base for all Pydantic DTOs — strict, orjson-ready, camelCase aliased."""

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        str_strip_whitespace=True,
        use_enum_values=True,
    )


class TimestampMixin(BaseDTO):
    created_at: datetime
    updated_at: datetime


class TenantScopedDTO(TimestampMixin):
    tenant_id: UUID


class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


class PaginatedResponse(BaseDTO, Generic[T]):
    """Standard paginated response envelope."""

    items: list[T]
    total: int
    page: int
    page_size: int
    total_pages: int

    @classmethod
    def create(
        cls,
        items: list[T],
        total: int,
        page: int,
        page_size: int,
    ) -> PaginatedResponse[T]:
        total_pages = max(1, (total + page_size - 1) // page_size)
        return cls(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )


class APIResponse(BaseDTO, Generic[T]):
    """Standard API response envelope."""

    success: bool = True
    data: T | None = None
    error: str | None = None
    request_id: str | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    @classmethod
    def ok(cls, data: T, request_id: str | None = None) -> APIResponse[T]:
        return cls(success=True, data=data, request_id=request_id)

    @classmethod
    def fail(cls, error: str, request_id: str | None = None) -> APIResponse[None]:
        return cls(success=False, error=error, request_id=request_id)


class MoneyAmount(BaseDTO):
    """Immutable money representation — always integer minor units (paise/cents)."""

    amount_minor: int = Field(
        ..., description="Amount in smallest currency unit (e.g. paise for INR)"
    )
    currency: str = Field(default="INR", min_length=3, max_length=3)

    @property
    def amount_major(self) -> float:
        if self.currency == "INR":
            return self.amount_minor / 100
        return self.amount_minor / 100  # extend for other currencies
