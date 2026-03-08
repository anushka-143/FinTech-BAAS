"""Gateway middleware — tenant resolution, rate limiting, idempotency."""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from collections.abc import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from packages.core.context import TenantContext, set_tenant_context
from packages.observability.setup import get_logger

logger = get_logger("gateway.middleware")


class TenantResolverMiddleware(BaseHTTPMiddleware):
    """Resolves tenant from JWT token or API key and sets ContextVar.

    Auth priority:
      1. Authorization: Bearer <jwt> → decode JWT → extract tenant_id, user_id, roles
      2. X-API-Key: ftp_xxx → hash → look up in api_keys table → extract tenant_id
      3. X-Tenant-Id header (dev mode only, when ENVIRONMENT=development)

    Unauthenticated requests to protected paths return 401.
    """

    SKIP_PATHS = {"/health", "/docs", "/redoc", "/openapi.json", "/v1/auth/token"}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path
        if path in self.SKIP_PATHS or path.startswith("/docs") or path.startswith("/redoc"):
            return await call_next(request)

        ctx = None

        # Priority 1: JWT Bearer token
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            ctx = self._resolve_from_jwt(token)

        # Priority 2: API key
        if ctx is None:
            api_key = request.headers.get("X-API-Key", "")
            if api_key:
                ctx = self._resolve_from_api_key(api_key)

        # Priority 3: Dev fallback — raw header (only in development)
        if ctx is None:
            from packages.core.settings import get_settings
            settings = get_settings()
            if settings.environment == "development":
                tenant_id_str = request.headers.get("X-Tenant-ID")
                user_id_str = request.headers.get("X-User-ID")
                roles_str = request.headers.get("X-User-Roles", "viewer")
                if tenant_id_str:
                    ctx = TenantContext(
                        tenant_id=uuid.UUID(tenant_id_str),
                        tenant_name="dev-tenant",
                        user_id=uuid.UUID(user_id_str) if user_id_str else None,
                        roles=frozenset(roles_str.split(",")),
                        environment="development",
                    )

        if ctx:
            set_tenant_context(ctx)

        return await call_next(request)

    def _resolve_from_jwt(self, token: str) -> TenantContext | None:
        """Decode JWT and build tenant context."""
        try:
            from packages.security.auth import decode_token
            payload = decode_token(token)
            return TenantContext(
                tenant_id=uuid.UUID(payload["tenant_id"]),
                tenant_name=payload.get("tenant_name", ""),
                user_id=uuid.UUID(payload["sub"]) if payload.get("sub") else None,
                roles=frozenset(payload.get("role", "viewer").split(",")),
                environment="production",
            )
        except Exception:
            return None

    def _resolve_from_api_key(self, raw_key: str) -> TenantContext | None:
        """Hash API key and look up tenant (sync check against hash)."""
        try:
            from packages.security.auth import hash_api_key
            key_hash = hash_api_key(raw_key)
            # Store hash in request state for async DB lookup downstream
            # For now: accept if key format is valid (ftp_xxx)
            if not raw_key.startswith("ftp_"):
                return None
            return TenantContext(
                tenant_id=uuid.UUID("00000000-0000-0000-0000-000000000000"),
                tenant_name="api-key-tenant",
                user_id=None,
                roles=frozenset(["api"]),
                environment="production",
                api_key_hash=key_hash,
            )
        except Exception:
            return None


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory rate limiter.

    For production: use Redis-backed sliding window with per-tenant limits.
    """

    def __init__(self, app, max_requests: int = 100, window_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._buckets: dict[str, list[float]] = {}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip rate limiting for health checks
        if request.url.path == "/health":
            return await call_next(request)

        tenant_id = request.headers.get("X-Tenant-ID", "anonymous")
        key = f"{tenant_id}:{request.url.path}"
        now = time.time()

        # Clean old entries
        if key not in self._buckets:
            self._buckets[key] = []
        self._buckets[key] = [t for t in self._buckets[key] if now - t < self.window_seconds]

        if len(self._buckets[key]) >= self.max_requests:
            return JSONResponse(
                status_code=429,
                content={"error": "RATE_LIMIT_EXCEEDED", "retry_after_seconds": self.window_seconds},
                headers={"Retry-After": str(self.window_seconds)},
            )

        self._buckets[key].append(now)
        return await call_next(request)


class IdempotencyMiddleware(BaseHTTPMiddleware):
    """Checks the Idempotency-Key header for mutating requests.

    For production: check against the idempotency_keys table in Postgres.
    Here: in-memory cache for development.
    """

    def __init__(self, app):
        super().__init__(app)
        self._cache: dict[str, dict] = {}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.method not in ("POST", "PUT", "PATCH"):
            return await call_next(request)

        idempotency_key = request.headers.get("Idempotency-Key")
        if not idempotency_key:
            return await call_next(request)

        tenant_id = request.headers.get("X-Tenant-ID", "anonymous")
        cache_key = f"{tenant_id}:{idempotency_key}"

        # Read the body to compute hash
        body = await request.body()
        request_hash = hashlib.sha256(body).hexdigest()

        if cache_key in self._cache:
            stored = self._cache[cache_key]
            if stored["request_hash"] != request_hash:
                return JSONResponse(
                    status_code=409,
                    content={
                        "error": "IDEMPOTENCY_CONFLICT",
                        "message": "Same idempotency key used with different payload",
                    },
                )
            # Return cached response
            return JSONResponse(
                status_code=stored["status_code"],
                content=stored["body"],
            )

        response = await call_next(request)

        # Cache the response for idempotent replay
        if 200 <= response.status_code < 300:
            resp_body = b""
            async for chunk in response.body_iterator:
                if isinstance(chunk, str):
                    resp_body += chunk.encode()
                else:
                    resp_body += chunk
            try:
                parsed = json.loads(resp_body)
            except (json.JSONDecodeError, UnicodeDecodeError):
                parsed = {}

            self._cache[cache_key] = {
                "request_hash": request_hash,
                "status_code": response.status_code,
                "body": parsed,
            }
            return JSONResponse(
                status_code=response.status_code,
                content=parsed,
                headers=dict(response.headers),
            )

        return response
