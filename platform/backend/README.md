# AI-Native Fintech Infrastructure Platform

> A secure multi-tenant fintech SaaS platform with a deterministic financial core
> and an embedded AI intelligence layer. Not a chatbot — AI is built into
> KYC review, payout triage, reconciliation, risk analysis, and developer support.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│ API Gateway (FastAPI)                                           │
│  Auth → Tenant → RBAC → Rate Limit → Idempotency → Tracing    │
├─────────────────────────────────────────────────────────────────┤
│                  Deterministic Financial Core                    │
│  Auth │ KYC │ Collections │ Payouts │ Ledger │ Recon │ Risk    │
│  Webhooks │ Audit │ Notifications                               │
├─────────────────────────────────────────────────────────────────┤
│                    AI Intelligence Layer                         │
│  Document AI (OCR+Tamper) │ Smart Payout Routing │ Recon AI    │
│  Liveness/Deepfake │ Name Matching │ Categorization             │
│  Forecasting │ Explainable Risk │ Collections AI                │
│  AI Cost Router │ Circuit Breakers │ Copilots                   │
├─────────────────────────────────────────────────────────────────┤
│                  Async & Event Backbone                         │
│  Temporal Workflows │ Transactional Outbox │ Domain Events      │
├─────────────────────────────────────────────────────────────────┤
│                    Data Layer                                    │
│  PostgreSQL (+read replica) │ Redis │ MinIO │ Supabase        │
└─────────────────────────────────────────────────────────────────┘
```

## Stack

| Layer         | Technology                          |
|---------------|-------------------------------------|
| Language      | Python 3.12                         |
| API           | FastAPI + Pydantic v2               |
| Server        | Uvicorn + uvloop                    |
| Database      | PostgreSQL 17 (pgvector)            |
| ORM           | SQLAlchemy 2 async + asyncpg        |
| Migrations    | Alembic                             |
| Cache         | Redis 8                             |
| Events        | Redpanda (Kafka API)                |
| Workflows     | Temporal                            |
| Object Store  | MinIO (S3 API)                      |
| OCR           | PaddleOCR 3.0 (PP-StructureV3)     |
| AI            | Google Gemini 2.5 Pro + function calling |
| Observability | OpenTelemetry + structlog           |
| Linting       | Ruff                                |

## Services (14 routers mounted in gateway)

### Deterministic Core
| Service        | Prefix              | Purpose                              |
|----------------|----------------------|--------------------------------------|
| Auth           | `/v1/auth`           | JWT tokens, API key CRUD             |
| Ledger         | `/v1/ledger`         | Double-entry journals, balances, holds|
| Payouts        | `/v1/payouts`        | Indian rails (UPI/IMPS/NEFT/RTGS)   |
| Collections    | `/v1/...`            | Virtual accounts, UPI links, QR codes|
| KYC            | `/v1/kyc`            | Indian docs (Aadhaar/PAN/GSTIN/CIN) |
| Risk           | `/v1/risk`           | PMLA rules, sanctions, AML scoring   |
| Reconciliation | `/v1/recon`          | Statement matching, break analysis   |
| Webhooks       | `/v1/webhooks`       | Endpoint CRUD, DLQ, replay           |
| Audit          | `/v1/audit`          | Immutable audit log                  |
| Notifications  | `/v1/notifications`  | Email, SMS, in-app with templates    |

### AI Intelligence Layer
| Service        | Prefix               | Purpose                             |
|----------------|----------------------|--------------------------------------|
| Document AI    | `/v1/document-ai`    | OCR extraction, tamper detection     |
| AI Agents      | `/v1/ai`             | Triage, review, analysis, copilots   |
| Forecasting    | `/v1/ledger`         | AI cashflow predictions              |
| Risk Pre-check | `/v1/risk`           | Sync risk scoring for real-time rails|

## AI Philosophy

```
AI prepares, explains, prioritizes, and recommends.
The deterministic core decides, records, and executes.
Cost routing: deterministic first, LLM only for exceptions.
Forced grounding: AI must cite exact source records.
```

AI is embedded in 16 workflows:
1. **KYC Review** — extraction + mismatch detection + review summary
2. **Payout Triage** — failure classification + retryability + next action
3. **Recon Analysis** — break explanation + resolution path
4. **Risk/AML** — anomaly explanation + alert prioritization
5. **Ops Copilot** — case context + investigation assistance
6. **Developer Copilot** — auto-synced from OpenAPI spec
7. **Smart Payout Routing** — optimal rail selection (UPI/IMPS/NEFT/RTGS)
8. **Beneficiary Name Matching** — fuzzy matching for RBI mandate
9. **Transaction Categorization** — India-specific NLP categorization
10. **Cashflow Forecasting** — trend, seasonality, anomaly detection
11. **Liveness / Deepfake Defense** — passive + active + GAN detection
12. **Explainable Risk Queues** — rule contribution breakdown
13. **AI-Native Reconciliation** — smart matching + fee patterns
14. **AI Collections Intelligence** — prioritization + payment prediction
15. **Document Tamper Detection** — font, edge, metadata analysis
16. **Defensive Circuit Breakers** — AI-triggered reversible protections

## Quick Start

```bash
# 1. Start infrastructure
docker compose up -d

# 2. Install dependencies
cd backend && pip install -e ".[dev,ai,ocr]"

# 3. Run migrations
alembic upgrade head

# 4. Seed demo data
python -m packages.db.seed

# 5. Start server
uvicorn apps.gateway.main:app --reload --host 0.0.0.0 --port 8000

# 6. Open docs
open http://localhost:8000/docs
```

## Project Structure

```
platform/
├── backend/
│   ├── apps/                     # Service modules
│   │   ├── gateway/              # FastAPI app + middleware
│   │   ├── auth/                 # JWT + API keys
│   │   ├── ledger/               # Double-entry accounting
│   │   ├── payouts/              # Payout lifecycle
│   │   ├── collections/          # Virtual accounts + UPI
│   │   ├── kyc/                  # KYC/KYB verification
│   │   ├── risk/                 # Rules + AML + sanctions
│   │   ├── recon/                # Reconciliation
│   │   ├── webhooks/             # Webhook CRUD + DLQ
│   │   ├── audit/                # Immutable audit log
│   │   ├── notifications/        # Email/SMS/in-app
│   │   ├── document_ai/          # OCR + extraction
│   │   └── ai_agents/            # AI orchestrator + copilots
│   ├── packages/                 # Shared libraries
│   │   ├── core/                 # Models, errors, context, settings
│   │   ├── db/                   # Engine, migrations, seed
│   │   ├── schemas/              # SQLAlchemy models
│   │   ├── security/             # JWT, HMAC, RBAC/ABAC
│   │   ├── events/               # Domain events + outbox
│   │   ├── observability/        # OTel + structlog
│   │   ├── providers/            # Banking partner adapters
│   │   └── workflows/            # Temporal workflow definitions
│   ├── tests/                    # Test suite
│   ├── pyproject.toml            # Dependencies
│   ├── alembic.ini               # Migration config
│   └── .env                      # Environment config
├── docker-compose.yml            # Local infra
└── README.md
```
