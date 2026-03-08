"""Developer Copilot Context Generator — auto-synced from OpenAPI spec.

Prevents context drift: the copilot always answers with current API info
because its knowledge base is generated from the live app schema, not
from manually maintained docs.

On app startup (or first call), reads app.openapi() and produces a
structured context document the LLM uses for developer queries.
"""

from __future__ import annotations

from typing import Any

_cached_context: dict[str, Any] | None = None


class CopilotContextGenerator:
    """Generates copilot context from the live OpenAPI schema.

    This ensures the developer copilot never gives stale API info.
    If an engineer updates an endpoint or payload, the copilot
    automatically reflects the change on next restart.
    """

    @classmethod
    def get_context(cls) -> dict[str, Any]:
        """Return structured API context for the developer copilot.

        Caches on first call — context regenerates on app restart.
        """
        global _cached_context
        if _cached_context is not None:
            return _cached_context

        try:
            _cached_context = cls._generate_from_openapi()
        except Exception:
            # Graceful fallback if app isn't fully loaded yet
            _cached_context = cls._fallback_context()

        return _cached_context

    @classmethod
    def _generate_from_openapi(cls) -> dict[str, Any]:
        """Read the live FastAPI OpenAPI schema and extract endpoint info."""
        from apps.gateway.main import app

        schema = app.openapi()
        endpoints = []

        for path, methods in schema.get("paths", {}).items():
            for method, detail in methods.items():
                if method in ("get", "post", "put", "patch", "delete"):
                    endpoints.append({
                        "path": path,
                        "method": method.upper(),
                        "summary": detail.get("summary", ""),
                        "description": detail.get("description", ""),
                        "tags": detail.get("tags", []),
                        "parameters": [
                            {"name": p["name"], "in": p["in"], "required": p.get("required", False)}
                            for p in detail.get("parameters", [])
                        ],
                        "request_body": bool(detail.get("requestBody")),
                        "responses": list(detail.get("responses", {}).keys()),
                    })

        # Extract common schemas for developer reference
        schemas = {}
        for name, schema_def in schema.get("components", {}).get("schemas", {}).items():
            schemas[name] = {
                "type": schema_def.get("type", "object"),
                "properties": list(schema_def.get("properties", {}).keys()),
                "required": schema_def.get("required", []),
            }

        return {
            "api_version": schema.get("info", {}).get("version", "0.1.0"),
            "title": schema.get("info", {}).get("title", ""),
            "endpoints": endpoints,
            "total_endpoints": len(endpoints),
            "schemas": schemas,
            "total_schemas": len(schemas),
            "tags": sorted({tag for ep in endpoints for tag in ep["tags"]}),
            "auth_header": "X-Tenant-Id (required for all tenant-scoped endpoints)",
            "base_url": "/v1",
        }

    @classmethod
    def _fallback_context(cls) -> dict[str, Any]:
        """Minimal fallback if OpenAPI isn't available yet."""
        return {
            "endpoints": [],
            "total_endpoints": 0,
            "schemas": {},
            "tags": [
                "Auth", "Ledger", "Payouts", "Collections", "KYC",
                "Risk", "Reconciliation", "Webhooks", "Audit",
                "AI Agents", "Document AI", "Notifications", "Forecasting",
            ],
            "auth_header": "X-Tenant-Id",
            "base_url": "/v1",
            "note": "Full context unavailable — app may not be fully loaded",
        }

    @classmethod
    def invalidate_cache(cls) -> None:
        """Clear cached context — call when routes change at runtime."""
        global _cached_context
        _cached_context = None
