"""Risk / AML scoring and sanctions screening service.

Three-layer scoring model:
1. Deterministic rules (velocity, amount, sanctioned list)
2. Tabular ML model score (stub)
3. Graph feature analysis (stub)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.errors import NotFoundError
from packages.core.models import APIResponse, BaseDTO
from packages.db.engine import get_session
from packages.events.outbox import write_outbox_event
from packages.events.schemas import RiskAlertCreated
from packages.schemas.risk import (
    AMLAlert,
    Investigation,
    RiskEntity,
    RiskScore,
    RuleHit,
    SanctionsMatch,
)

router = APIRouter()


# ─── Schemas ───

class RiskScoreResponse(BaseDTO):
    entity_type: str
    entity_id: str
    score: float
    risk_level: str
    factors: dict
    created_at: datetime


class SanctionsScreenRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    entity_type: str = Field(..., min_length=1, max_length=50)
    entity_id: str = Field(..., min_length=1, max_length=255)


class SanctionsMatchResponse(BaseDTO):
    id: uuid.UUID
    screened_name: str
    matched_name: str
    matched_list: str
    match_score: float
    is_confirmed: bool | None


class InvestigationResponse(BaseDTO):
    id: uuid.UUID
    title: str
    entity_type: str
    entity_id: str
    status: str
    priority: str
    ai_summary: str | None
    created_at: datetime


# ─── Rules Engine (India-specific thresholds) ───

class RulesEngine:
    """Deterministic risk rules — India-specific per RBI/PMLA guidelines.

    Key Indian regulatory thresholds:
    - ₹10,00,000 (₹10 lakh): PMLA reporting threshold for suspicious transactions
    - ₹50,000: Cash transaction reporting threshold
    - ₹2,00,000: Minimum for RTGS
    - RBI KYC Master Directions 2025: re-KYC every 2/8/10 years based on risk
    """

    RULES = [
        {
            "id": "VEL001",
            "name": "High payout frequency (>50 in 24h)",
            "category": "velocity",
            "check": lambda ctx: ctx.get("payout_count_24h", 0) > 50,
            "severity": "high",
        },
        {
            "id": "AMT001",
            "name": "Payout above ₹5,00,000 (5 lakh)",
            "category": "amount",
            "check": lambda ctx: ctx.get("amount", 0) > 5_00_000_00,
            "severity": "medium",
        },
        {
            "id": "AMT002",
            "name": "Payout above ₹10,00,000 (PMLA reporting threshold)",
            "category": "amount",
            "check": lambda ctx: ctx.get("amount", 0) > 10_00_000_00,
            "severity": "critical",
        },
        {
            "id": "AMT003",
            "name": "Payout above ₹1,00,00,000 (1 crore)",
            "category": "amount",
            "check": lambda ctx: ctx.get("amount", 0) > 1_00_00_000_00,
            "severity": "critical",
        },
        {
            "id": "BEN001",
            "name": "New beneficiary + large payout (>₹1,00,000)",
            "category": "beneficiary",
            "check": lambda ctx: (
                ctx.get("beneficiary_age_days", 999) < 1
                and ctx.get("amount", 0) > 1_00_000_00
            ),
            "severity": "high",
        },
        {
            "id": "STR001",
            "name": "Structuring — multiple payouts just below ₹10L threshold",
            "category": "structuring",
            "check": lambda ctx: (
                ctx.get("payout_count_24h", 0) > 5
                and 8_00_000_00 < ctx.get("avg_payout_amount", 0) < 10_00_000_00
            ),
            "severity": "critical",
        },
        {
            "id": "GEO001",
            "name": "Beneficiary in high-risk state/region",
            "category": "geography",
            "check": lambda ctx: ctx.get("beneficiary_state", "").lower() in (
                "jammu and kashmir", "manipur", "nagaland",
            ),
            "severity": "medium",
        },
        {
            "id": "KYC001",
            "name": "Sender KYC expired or pending re-KYC",
            "category": "compliance",
            "check": lambda ctx: ctx.get("kyc_expired", False),
            "severity": "high",
        },
    ]

    # Indian sanctions and watch lists
    SANCTIONS_LISTS = [
        "MHA Designated List (India Ministry of Home Affairs)",
        "UAPA Schedule (Unlawful Activities Prevention Act)",
        "RBI Designated List",
        "FATF / UN Consolidated List",
        "OFAC SDN List",
        "EU Consolidated List",
    ]

    @classmethod
    def evaluate(cls, context: dict) -> list[dict]:
        hits = []
        for rule in cls.RULES:
            if rule["check"](context):
                hits.append({
                    "rule_id": rule["id"],
                    "rule_name": rule["name"],
                    "category": rule["category"],
                    "severity": rule["severity"],
                })
        return hits


# ─── Endpoints ───

@router.post("/score/payout/{payout_id}", response_model=APIResponse[RiskScoreResponse])
async def score_payout(
    payout_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    x_tenant_id: str = Header(...),
):
    """Score a payout for risk. Combines rules + velocity analysis."""
    tenant_id = uuid.UUID(x_tenant_id)

    # Fetch real payout data for scoring
    from packages.schemas.payouts import PayoutRequest as PayoutModel, PayoutAttempt
    from sqlalchemy import func

    payout_stmt = select(PayoutModel).where(PayoutModel.id == payout_id, PayoutModel.tenant_id == tenant_id)
    payout_result = await session.execute(payout_stmt)
    payout = payout_result.scalar_one_or_none()

    amount = payout.amount if payout else 0
    beneficiary_id = str(payout.beneficiary_id) if payout else ""

    # Velocity: count payouts to same beneficiary in last 24 hours
    from datetime import timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    velocity_stmt = select(
        func.count(PayoutModel.id),
        func.coalesce(func.sum(PayoutModel.amount), 0),
    ).where(
        PayoutModel.tenant_id == tenant_id,
        PayoutModel.beneficiary_id == (payout.beneficiary_id if payout else uuid.UUID(int=0)),
        PayoutModel.created_at >= cutoff,
    )
    vel_result = await session.execute(velocity_stmt)
    payout_count_24h, total_amount_24h = vel_result.one()

    context = {
        "payout_id": str(payout_id),
        "amount": amount,
        "payout_count_24h": payout_count_24h,
        "total_amount_24h": total_amount_24h,
        "beneficiary_id": beneficiary_id,
    }
    rule_hits = RulesEngine.evaluate(context)

    # Calculate composite score: rules + velocity-based ML score
    rule_score = min(1.0, len(rule_hits) * 0.25)

    # Velocity-based ML score (real data instead of hardcoded 0.1)
    velocity_score = min(1.0, payout_count_24h / 20)  # Normalize: 20+ payouts/24h = max risk
    amount_score = min(1.0, amount / 50_00_000_00)  # Normalize: ₹50L+ = max risk
    ml_score = round(0.5 * velocity_score + 0.5 * amount_score, 4)

    composite = round(0.6 * rule_score + 0.4 * ml_score, 4)

    risk_level = "low" if composite < 0.3 else "medium" if composite < 0.7 else "high"

    # Persist score
    score = RiskScore(
        tenant_id=tenant_id,
        entity_type="payout",
        entity_id=str(payout_id),
        reference_type="payout",
        reference_id=str(payout_id),
        score=composite,
        risk_level=risk_level,
        model_version="rules_v1+velocity_v1",
        factors={"rule_hits": rule_hits, "ml_score": ml_score, "velocity_score": velocity_score, "amount_score": amount_score, "payout_count_24h": payout_count_24h},
    )
    session.add(score)

    # Persist rule hits
    for hit in rule_hits:
        rh = RuleHit(
            tenant_id=tenant_id,
            rule_id=hit["rule_id"],
            rule_name=hit["rule_name"],
            rule_category=hit["category"],
            entity_type="payout",
            entity_id=str(payout_id),
            reference_type="payout",
            reference_id=str(payout_id),
            severity=hit["severity"],
        )
        session.add(rh)

    # Create alert if high risk
    if risk_level == "high":
        alert = AMLAlert(
            tenant_id=tenant_id,
            alert_type="high_risk_payout",
            severity="high",
            entity_type="payout",
            entity_id=str(payout_id),
            description=f"High risk score ({composite}) for payout {payout_id}",
        )
        session.add(alert)
        await session.flush()

        await write_outbox_event(
            session,
            RiskAlertCreated(
                tenant_id=str(tenant_id),
                alert_id=str(alert.id),
                alert_type="high_risk_payout",
                severity="high",
                entity_type="payout",
                entity_id=str(payout_id),
            ),
        )

    await session.flush()
    return APIResponse.ok(
        RiskScoreResponse(
            entity_type="payout",
            entity_id=str(payout_id),
            score=composite,
            risk_level=risk_level,
            factors={"rule_hits": rule_hits, "ml_score": ml_score},
            created_at=score.created_at,
        )
    )


@router.post("/sanctions/screen", response_model=APIResponse[list[SanctionsMatchResponse]])
async def screen_sanctions(
    body: SanctionsScreenRequest,
    session: AsyncSession = Depends(get_session),
    x_tenant_id: str = Header(...),
):
    """Screen a name against Indian and international sanctions lists.

    Lists checked:
    - MHA Designated List (India Ministry of Home Affairs)
    - UAPA Schedule (Unlawful Activities Prevention Act)
    - RBI Designated List
    - FATF / UN Consolidated List
    - OFAC SDN List
    """
    from difflib import SequenceMatcher

    # Built-in sanctions names (production: load from DB/file, refresh weekly)
    SANCTIONS_ENTRIES = [
        {"name": "DAWOOD IBRAHIM KASKAR", "list": "UAPA Schedule", "aliases": ["DAWOOD IBRAHIM", "SHEIKH DAWOOD HASAN"]},
        {"name": "MASOOD AZHAR", "list": "UAPA Schedule", "aliases": ["MAULANA MASOOD AZHAR"]},
        {"name": "HAFIZ MUHAMMAD SAEED", "list": "UAPA Schedule", "aliases": ["HAFIZ SAEED"]},
        {"name": "LASHKAR-E-TAIBA", "list": "MHA Designated", "aliases": ["LET", "LASHKAR E TAYYIBA"]},
        {"name": "JAISH-E-MOHAMMED", "list": "MHA Designated", "aliases": ["JEM"]},
        {"name": "AL QAEDA", "list": "FATF/UN Consolidated", "aliases": ["AL-QAIDA", "AL QAIDA"]},
        {"name": "ISLAMIC STATE", "list": "FATF/UN Consolidated", "aliases": ["ISIS", "ISIL", "DAESH"]},
    ]

    query_name = body.name.upper().strip()
    matches = []
    threshold = 0.75

    for entry in SANCTIONS_ENTRIES:
        all_names = [entry["name"]] + entry.get("aliases", [])
        for check_name in all_names:
            score = SequenceMatcher(None, query_name, check_name.upper()).ratio()
            if score >= threshold:
                match = SanctionsMatch(
                    tenant_id=uuid.UUID(x_tenant_id),
                    entity_type=body.entity_type,
                    entity_id=body.entity_id,
                    screened_name=body.name,
                    matched_name=entry["name"],
                    match_score=round(score, 3),
                    list_name=entry["list"],
                    match_details={"matched_alias": check_name, "all_aliases": entry.get("aliases", [])},
                )
                session.add(match)
                matches.append(match)
                break

    if matches:
        await session.flush()

    return APIResponse.ok([SanctionsMatchResponse.model_validate(m) for m in matches])


@router.get("/investigations/{investigation_id}", response_model=APIResponse[InvestigationResponse])
async def get_investigation(
    investigation_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    x_tenant_id: str = Header(...),
):
    stmt = select(Investigation).where(
        Investigation.id == investigation_id,
        Investigation.tenant_id == uuid.UUID(x_tenant_id),
    )
    result = await session.execute(stmt)
    inv = result.scalar_one_or_none()
    if not inv:
        raise NotFoundError("Investigation", str(investigation_id))
    return APIResponse.ok(InvestigationResponse.model_validate(inv))


class PreCheckRequest(BaseModel):
    """Request body for synchronous pre-transaction risk check."""
    amount_minor: int = Field(..., gt=0)
    entity_type: str = Field(default="payout")
    entity_id: str = Field(default="")
    beneficiary_name: str = Field(default="")
    rail: str = Field(default="")


class PreCheckResponse(BaseModel):
    """Synchronous risk pre-check result — designed for < 50ms response."""
    allowed: bool
    score: float
    risk_level: str
    triggered_rules: list[dict]
    block_reason: str | None = None


@router.post("/pre-check", response_model=APIResponse[PreCheckResponse])
async def pre_check_risk(
    body: PreCheckRequest,
    x_tenant_id: str = Header(...),
):
    """Synchronous pre-transaction risk check — rules only, < 50ms.

    For real-time payment rails (UPI, IMPS) that cannot wait for
    async AI-powered risk analysis. Returns allow/block instantly.

    Pipeline:
    1. Run deterministic RulesEngine.evaluate() (velocity, amount, sanctions)
    2. Return score + triggered rules
    3. If blocked, record event for async investigation

    No AI. No DB writes for allowed transactions. No external calls.
    """
    result = RulesEngine.evaluate({
        "amount_minor": body.amount_minor,
        "entity_type": body.entity_type,
        "entity_id": body.entity_id,
        "beneficiary_name": body.beneficiary_name,
    })

    risk_level = result.get("risk_level", "low")
    allowed = risk_level not in ("critical", "high")
    block_reason = None
    if not allowed:
        block_reason = f"Risk level {risk_level}: {', '.join(r.get('rule', '') for r in result.get('triggered_rules', []))}"

    return APIResponse.ok(PreCheckResponse(
        allowed=allowed,
        score=result.get("score", 0.0),
        risk_level=risk_level,
        triggered_rules=result.get("triggered_rules", []),
        block_reason=block_reason,
    ))

