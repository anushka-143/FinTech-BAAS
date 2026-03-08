"""Gateway FastAPI application factory.

This is the single entry point for all external requests. It composes the
middleware chain and mounts all service routers. In production, individual
services can be split into separate deployments — this monolith mode is
for development and early-stage deployment.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from packages.core.settings import get_settings
from packages.db.engine import dispose_engine
from packages.observability.middleware import RequestTracingMiddleware
from packages.observability.setup import setup_logging, setup_telemetry

from apps.gateway.error_handlers import register_error_handlers
from apps.gateway.middleware import (
    IdempotencyMiddleware,
    RateLimitMiddleware,
    TenantResolverMiddleware,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    setup_telemetry()
    setup_logging()

    # Create tables for new modules on startup (dev/early-stage only)
    try:
        from packages.db.engine import engine
        from packages.db.base import Base
        # Import all schemas so Base.metadata collects them
        import packages.schemas.embeddings  # noqa: F401
        import packages.workflows.state  # noqa: F401
        import packages.analytics.pipeline  # noqa: F401
        import packages.jobs.runner  # noqa: F401
        import packages.tenancy.isolation  # noqa: F401
        import apps.notifications.orchestrator  # noqa: F401
        import apps.document_ai.ingestion  # noqa: F401

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception:
        pass  # Tables may already exist

    yield
    await dispose_engine()


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="AI Fintech Infrastructure Platform",
        description="AI-Native BaaS Platform — multi-tenant fintech infrastructure with AI intelligence layer",
        version="0.1.0",
        docs_url="/docs" if settings.environment != "production" else None,
        redoc_url="/redoc" if settings.environment != "production" else None,
        lifespan=lifespan,
    )

    # ─── Middleware (outermost → innermost) ───
    # NOTE: In FastAPI/Starlette, the LAST add_middleware call becomes the
    # OUTERMOST middleware (runs first). CORS must be outermost to handle
    # OPTIONS preflight before other middleware touches the request.
    app.add_middleware(IdempotencyMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(TenantResolverMiddleware)
    app.add_middleware(RequestTracingMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ─── Error handlers ───
    register_error_handlers(app)

    # ─── Routers ───

    # Existing domain routers
    from apps.auth.router import router as auth_router
    from apps.ledger.router import router as ledger_router
    from apps.payouts.router import router as payouts_router
    from apps.collections.router import router as collections_router
    from apps.kyc.router import router as kyc_router
    from apps.risk.router import router as risk_router
    from apps.recon.router import router as recon_router
    from apps.webhooks.router import router as webhooks_router
    from apps.audit.router import router as audit_router
    from apps.ai_agents.router import router as ai_router
    from apps.document_ai.router import router as doc_ai_router
    from apps.notifications.router import router as notif_router
    from apps.ledger.forecasting_router import router as forecast_router

    # New architecture routers
    from apps.approvals.router import router as approvals_router
    from apps.policy.router import router as policy_router
    from apps.cases.router import router as cases_router
    from apps.bff.router import router as bff_router
    from apps.realtime.router import router as realtime_router

    # Domain services
    app.include_router(auth_router, prefix="/v1/auth", tags=["Auth"])
    app.include_router(ledger_router, prefix="/v1/ledger", tags=["Ledger"])
    app.include_router(payouts_router, prefix="/v1/payouts", tags=["Payouts"])
    app.include_router(collections_router, prefix="/v1", tags=["Collections"])
    app.include_router(kyc_router, prefix="/v1/kyc", tags=["KYC"])
    app.include_router(risk_router, prefix="/v1/risk", tags=["Risk"])
    app.include_router(recon_router, prefix="/v1/recon", tags=["Reconciliation"])
    app.include_router(webhooks_router, prefix="/v1/webhooks", tags=["Webhooks"])
    app.include_router(audit_router, prefix="/v1/audit", tags=["Audit"])
    app.include_router(ai_router, prefix="/v1/ai", tags=["AI Agents"])
    app.include_router(doc_ai_router, prefix="/v1/document-ai", tags=["Document AI"])
    app.include_router(notif_router, prefix="/v1/notifications", tags=["Notifications"])
    app.include_router(forecast_router, prefix="/v1/ledger", tags=["Forecasting"])

    # Control & governance
    app.include_router(approvals_router, prefix="/v1/approvals", tags=["Approvals"])
    app.include_router(policy_router, prefix="/v1/policy", tags=["Policy Engine"])
    app.include_router(cases_router, prefix="/v1/cases", tags=["Case Management"])

    # Experience layer
    app.include_router(bff_router, prefix="/v1/bff", tags=["BFF"])
    app.include_router(realtime_router, prefix="/v1/realtime", tags=["Real-Time"])

    @app.get("/health", tags=["System"])
    async def health():
        return {"status": "ok", "service": "fintech-platform"}

    return app


app = create_app()
