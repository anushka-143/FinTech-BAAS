# AI Fintech Infrastructure Platform

**Decentro-aligned AI BaaS (Banking-as-a-Service) platform**

A production-grade, multi-tenant fintech infrastructure platform built with Python 3.12, FastAPI, PostgreSQL, and a tiered AI layer for document intelligence, risk scoring, and ops copilots.

---

## Architecture

```
┌──────────────────────────────────┐
│   Client Apps / Dashboard        │
│   Merchant Systems / Ops UI      │
└──────────────┬───────────────────┘
               │
        ┌──────▼──────┐
        │ API Gateway │   ← Auth, HMAC, Tenant, Rate-limit, Idempotency
        └──────┬──────┘
               │
  ┌────────────┼────────────────────────┐
  │            │                        │
  ▼            ▼                        ▼
KYC Svc    Collections Svc        Payouts Svc
  │            │                        │
  └────────────┼────────────────────────┘
               │
     ┌─────────┼─────────┐
     ▼                   ▼
  Ledger Svc        Risk / AML Svc
     │                   │
     └─────────┬─────────┘
               │
      Event Bus + Temporal
               │
    ┌──────────┼──────────┐
    ▼                     ▼
  PostgreSQL           Redis
  + pgvector          Cache/RL
```

## Stack

| Layer | Technology |
|-------|-----------|
| API Framework | FastAPI + Pydantic v2 |
| App Server | Uvicorn + uvloop |
| Database | PostgreSQL 17 + pgvector |
| Cache | Redis 8 |
| Events | Redpanda (Kafka-compatible) |
| Workflows | Temporal |
| Document AI | PaddleOCR + PP-StructureV3 |
| LLM | OpenAI Responses API / vLLM |
| LLM Gateway | LiteLLM |
| Observability | OpenTelemetry + Prometheus |
| Tooling | uv + Ruff |

## Services

| Service | Description |
|---------|------------|
| `gateway` | API entry point — middleware chain (auth, HMAC, tenant, rate-limit, idempotency) |
| `auth` | JWT tokens, API key management, session handling |
| `ledger` | Double-entry accounting — journals, postings, balances, holds |
| `payouts` | Payout lifecycle — beneficiaries, state machine, provider dispatch |
| `collections` | Virtual accounts, inbound payments, statement queries |
| `kyc` | KYC/KYB case management, document upload, verification pipeline |
| `risk` | Rules engine, ML scoring, sanctions screening, AML alerts |
| `recon` | Reconciliation — statement import, matching, break classification |
| `webhooks` | Inbound/outbound webhook management, delivery tracking, DLQ |
| `audit` | Immutable append-only audit log |
| `ai_agents` | Payout triage, recon investigation, KYC review, developer copilot |

## Quick Start

```bash
# 1. Start infrastructure
docker compose up -d

# 2. Install dependencies
cd platform/backend
pip install -e ".[dev]"

# 3. Run migrations
alembic upgrade head

# 4. Start the API server
uvicorn apps.gateway.main:app --reload --host 0.0.0.0 --port 8000
```

API docs: `http://localhost:8000/docs`

## Project Structure

```
platform/
├── backend/
│   ├── apps/                    # Service applications
│   │   ├── gateway/             # API gateway + middleware
│   │   ├── auth/                # Authentication service
│   │   ├── ledger/              # Double-entry ledger
│   │   ├── payouts/             # Payout orchestration
│   │   ├── collections/         # Virtual accounts + collections
│   │   ├── kyc/                 # KYC/KYB management
│   │   ├── risk/                # Risk scoring + AML
│   │   ├── recon/               # Reconciliation engine
│   │   ├── webhooks/            # Webhook management
│   │   ├── audit/               # Audit log service
│   │   └── ai_agents/           # AI copilot service
│   ├── packages/                # Shared libraries
│   │   ├── core/                # Base models, errors, context, settings
│   │   ├── db/                  # SQLAlchemy engine + migrations
│   │   ├── schemas/             # All SQLAlchemy table models
│   │   ├── security/            # Auth, HMAC, RBAC/ABAC
│   │   ├── events/              # Domain events + transactional outbox
│   │   ├── observability/       # OpenTelemetry + structured logging
│   │   ├── providers/           # Payment provider adapters
│   │   └── workflows/           # Temporal workflow definitions
│   ├── tests/                   # Unit + integration tests
│   ├── pyproject.toml
│   ├── ruff.toml
│   └── alembic.ini
├── docker-compose.yml           # Local infra (Postgres, Redis, Redpanda, Temporal, MinIO)
└── README.md
```

## Key Design Decisions

1. **Double-entry ledger** — Every financial transaction posts balanced journals (sum debits = sum credits). Balances are materialized with optimistic locking.

2. **Tenant isolation** — `tenant_id` is derived from auth context (ContextVar), never from request body. Every DB query filters by tenant.

3. **Transactional outbox** — Domain events are written to the `outbox_events` table in the same DB transaction as business data, then published to Redpanda by a background poller. No phantom events.

4. **Immutable audit trail** — All state changes produce append-only audit events with before/after state.

5. **AI safety** — AI agents are read-only. They can summarize, investigate, and recommend — but cannot execute payouts, post journals, or approve KYC cases.

6. **HMAC webhooks** — All webhook signatures include timestamps for replay protection with 5-minute tolerance.

7. **RBAC + ABAC** — 6 roles with 23 granular permissions, plus attribute-based policies (same-tenant, amount threshold, maker-checker).
