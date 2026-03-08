"""Structured application error hierarchy.

Every error carries a machine-readable code, human message, and optional context dict.
Services raise these; the gateway error handler maps them to HTTP status codes.
"""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    """Base application error."""

    status_code: int = 500
    error_code: str = "INTERNAL_ERROR"

    def __init__(
        self,
        message: str = "An internal error occurred",
        *,
        error_code: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if error_code:
            self.error_code = error_code
        self.context = context or {}


class NotFoundError(AppError):
    status_code = 404
    error_code = "NOT_FOUND"

    def __init__(self, resource: str, identifier: str, **kwargs: Any) -> None:
        super().__init__(
            f"{resource} '{identifier}' not found",
            context={"resource": resource, "identifier": identifier},
            **kwargs,
        )


class ConflictError(AppError):
    status_code = 409
    error_code = "CONFLICT"

    def __init__(self, message: str = "Resource conflict", **kwargs: Any) -> None:
        super().__init__(message, **kwargs)


class IdempotencyConflictError(ConflictError):
    error_code = "IDEMPOTENCY_CONFLICT"

    def __init__(self, idempotency_key: str) -> None:
        super().__init__(
            f"Idempotency key '{idempotency_key}' already used with different request payload",
            context={"idempotency_key": idempotency_key},
        )


class ValidationError(AppError):
    status_code = 422
    error_code = "VALIDATION_ERROR"


class AuthenticationError(AppError):
    status_code = 401
    error_code = "AUTHENTICATION_FAILED"

    def __init__(self, message: str = "Authentication required", **kwargs: Any) -> None:
        super().__init__(message, **kwargs)


class AuthorizationError(AppError):
    status_code = 403
    error_code = "FORBIDDEN"

    def __init__(self, message: str = "Insufficient permissions", **kwargs: Any) -> None:
        super().__init__(message, **kwargs)


class RateLimitError(AppError):
    status_code = 429
    error_code = "RATE_LIMIT_EXCEEDED"

    def __init__(self, retry_after_seconds: int = 60) -> None:
        super().__init__(
            "Rate limit exceeded",
            context={"retry_after_seconds": retry_after_seconds},
        )
        self.retry_after_seconds = retry_after_seconds


class InsufficientBalanceError(AppError):
    status_code = 422
    error_code = "INSUFFICIENT_BALANCE"

    def __init__(self, account_id: str, required: int, available: int) -> None:
        super().__init__(
            "Insufficient available balance",
            context={
                "account_id": account_id,
                "required_minor": required,
                "available_minor": available,
            },
        )


class LedgerImbalanceError(AppError):
    status_code = 500
    error_code = "LEDGER_IMBALANCE"

    def __init__(self, debit_total: int, credit_total: int) -> None:
        super().__init__(
            f"Journal imbalance: debits={debit_total} credits={credit_total}",
            context={"debit_total": debit_total, "credit_total": credit_total},
        )


class ProviderError(AppError):
    status_code = 502
    error_code = "PROVIDER_ERROR"

    def __init__(self, provider: str, message: str, **kwargs: Any) -> None:
        super().__init__(
            f"Provider '{provider}' error: {message}",
            context={"provider": provider},
            **kwargs,
        )


class WebhookSignatureError(AppError):
    status_code = 401
    error_code = "WEBHOOK_SIGNATURE_INVALID"

    def __init__(self) -> None:
        super().__init__("Webhook signature verification failed")
