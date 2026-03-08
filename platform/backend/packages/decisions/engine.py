"""Decision Engine — separates signals, scores, recommendations, decisions.

In fintech, every critical action must trace:
  signal → score → recommendation → decision → execution

This separation enables auditability, explainability, and override capability.

Domains:
  - KYC: OCR signal + anomaly signal + sanctions hit → risk score → recommendation → decision
  - Payouts: risk score + policy result + balance check + approval status → execute/hold/reject
  - Recon: match signal + amount delta + timing → classification → resolution recommendation
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from sqlalchemy import Column, DateTime, String, Float, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from packages.db.base import Base, TimestampMixin


# ─── Schema ───

class DecisionRecord(Base, TimestampMixin):
    """Immutable record of a decision with full evidence chain."""
    __tablename__ = "decision_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    # What domain this decision belongs to
    domain = Column(String(50), nullable=False, index=True,
                    comment="kyc | payout | recon | risk | compliance")
    resource_type = Column(String(50), nullable=False)
    resource_id = Column(String(200), nullable=False, index=True)

    # Signals (raw inputs)
    signals = Column(JSONB, nullable=False, server_default='[]',
                     comment="Array of {source, signal_type, value, confidence}")

    # Scores (derived from signals)
    scores = Column(JSONB, nullable=False, server_default='{}',
                    comment="{risk_score, compliance_score, match_score, ...}")

    # Recommendation (what the system suggests)
    recommendation = Column(String(50), nullable=False,
                            comment="approve | reject | hold | review | escalate")
    recommendation_reason = Column(Text, nullable=True)
    recommendation_confidence = Column(Float, nullable=False, default=0.0)

    # Decision (what actually happened — may differ from recommendation if overridden)
    decision = Column(String(50), nullable=False,
                      comment="approved | rejected | held | escalated | overridden")
    decided_by = Column(String(50), nullable=False, comment="system | human | ai | policy")
    decided_by_id = Column(UUID(as_uuid=True), nullable=True)
    decision_reason = Column(Text, nullable=True)
    decided_at = Column(DateTime(timezone=True), nullable=False)

    # Override tracking
    was_overridden = Column(String(10), default="no", comment="no | yes")
    override_reason = Column(Text, nullable=True)

    # Policy that was applied
    policy_result = Column(JSONB, nullable=True,
                           comment="Result from PolicyEngine evaluation")


# ─── Domain types ───

class DecisionAction(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"
    HOLD = "hold"
    REVIEW = "review"
    ESCALATE = "escalate"


@dataclass
class Signal:
    """A raw signal input to the decision engine."""
    source: str           # "ocr", "sanctions", "risk_model", "policy", "liveness"
    signal_type: str      # "document_anomaly", "name_match", "velocity_check"
    value: Any            # The actual signal value
    confidence: float     # 0.0 to 1.0
    metadata: dict = field(default_factory=dict)


@dataclass
class DecisionInput:
    """All inputs needed to make a decision."""
    domain: str
    resource_type: str
    resource_id: str
    tenant_id: str
    signals: list[Signal]
    policy_result: dict | None = None


@dataclass
class DecisionOutput:
    """The full decision output with evidence chain."""
    recommendation: str
    recommendation_confidence: float
    recommendation_reason: str
    signals_summary: list[dict]
    scores: dict
    policy_applied: dict | None = None


class DecisionEngine:
    """Evaluates signals → scores → recommendation.

    Does NOT execute the decision. Caller decides whether to follow
    the recommendation or override it.
    """

    def evaluate(self, input: DecisionInput) -> DecisionOutput:
        """Evaluate signals and produce a recommendation."""
        evaluators = {
            "kyc": self._evaluate_kyc,
            "payout": self._evaluate_payout,
            "recon": self._evaluate_recon,
            "risk": self._evaluate_risk,
        }

        evaluator = evaluators.get(input.domain, self._evaluate_generic)
        return evaluator(input)

    async def record_decision(
        self,
        input: DecisionInput,
        output: DecisionOutput,
        decision: str,
        decided_by: str,
        decided_by_id: str | None = None,
        override_reason: str | None = None,
    ) -> str:
        """Persist the decision with full evidence chain."""
        from packages.db.engine import get_session_factory

        record_id = uuid.uuid4()
        was_overridden = "yes" if decision != output.recommendation else "no"

        factory = get_session_factory()
        async with factory() as session:
            record = DecisionRecord(
                id=record_id,
                tenant_id=uuid.UUID(input.tenant_id),
                domain=input.domain,
                resource_type=input.resource_type,
                resource_id=input.resource_id,
                signals=[s.__dict__ for s in input.signals],
                scores=output.scores,
                recommendation=output.recommendation,
                recommendation_reason=output.recommendation_reason,
                recommendation_confidence=output.recommendation_confidence,
                decision=decision,
                decided_by=decided_by,
                decided_by_id=uuid.UUID(decided_by_id) if decided_by_id else None,
                decision_reason=override_reason or output.recommendation_reason,
                decided_at=datetime.now(timezone.utc),
                was_overridden=was_overridden,
                override_reason=override_reason,
                policy_result=output.policy_applied,
            )
            session.add(record)
            await session.commit()

        return str(record_id)

    def _evaluate_kyc(self, input: DecisionInput) -> DecisionOutput:
        signals = input.signals
        scores = {}

        # Aggregate signal scores by type
        doc_signals = [s for s in signals if s.source == "ocr"]
        sanction_signals = [s for s in signals if s.source == "sanctions"]
        liveness_signals = [s for s in signals if s.source == "liveness"]

        scores["document_confidence"] = (
            sum(s.confidence for s in doc_signals) / len(doc_signals) if doc_signals else 0.5
        )
        scores["sanctions_clear"] = all(
            s.value in (None, False, "no_match") for s in sanction_signals
        )
        scores["liveness_passed"] = all(
            s.confidence > 0.7 for s in liveness_signals
        ) if liveness_signals else True

        # Composite score
        composite = scores["document_confidence"]
        if not scores["sanctions_clear"]:
            composite *= 0.3  # Massive penalty for sanctions hit
        if not scores["liveness_passed"]:
            composite *= 0.5

        # Recommendation
        if composite >= 0.85 and scores["sanctions_clear"]:
            rec = DecisionAction.APPROVE
            reason = "All checks passed with high confidence"
        elif composite >= 0.50:
            rec = DecisionAction.REVIEW
            reason = "Moderate confidence — human review recommended"
        else:
            rec = DecisionAction.REJECT
            reason = "Low confidence or critical flags"

        return DecisionOutput(
            recommendation=rec.value,
            recommendation_confidence=round(composite, 4),
            recommendation_reason=reason,
            signals_summary=[{"source": s.source, "type": s.signal_type, "conf": s.confidence} for s in signals],
            scores=scores,
            policy_applied=input.policy_result,
        )

    def _evaluate_payout(self, input: DecisionInput) -> DecisionOutput:
        signals = input.signals
        scores = {}

        risk_signals = [s for s in signals if s.source == "risk_model"]
        balance_signals = [s for s in signals if s.source == "balance_check"]
        policy_signals = [s for s in signals if s.source == "policy"]

        scores["risk_score"] = max((s.confidence for s in risk_signals), default=0.0)
        scores["has_balance"] = any(s.value is True for s in balance_signals)
        scores["policy_allows"] = all(s.value != "deny" for s in policy_signals)

        if not scores["has_balance"]:
            return DecisionOutput(
                recommendation=DecisionAction.REJECT.value,
                recommendation_confidence=1.0,
                recommendation_reason="Insufficient balance",
                signals_summary=[],
                scores=scores,
            )

        if not scores["policy_allows"]:
            return DecisionOutput(
                recommendation=DecisionAction.REJECT.value,
                recommendation_confidence=1.0,
                recommendation_reason="Policy denied",
                signals_summary=[],
                scores=scores,
            )

        if scores["risk_score"] > 0.7:
            rec = DecisionAction.HOLD
            reason = f"High risk score: {scores['risk_score']}"
        elif any(s.value == "require_approval" for s in policy_signals):
            rec = DecisionAction.REVIEW
            reason = "Requires maker-checker approval"
        else:
            rec = DecisionAction.APPROVE
            reason = "All checks passed"

        return DecisionOutput(
            recommendation=rec.value,
            recommendation_confidence=1.0 - scores["risk_score"],
            recommendation_reason=reason,
            signals_summary=[],
            scores=scores,
        )

    def _evaluate_recon(self, input: DecisionInput) -> DecisionOutput:
        signals = input.signals
        scores = {}

        match_signals = [s for s in signals if s.signal_type == "match_score"]
        amount_signals = [s for s in signals if s.signal_type == "amount_delta"]

        scores["match_confidence"] = max((s.confidence for s in match_signals), default=0.0)
        scores["amount_delta_paise"] = next((s.value for s in amount_signals), 0)

        if scores["match_confidence"] > 0.90 and abs(scores["amount_delta_paise"]) < 100:
            rec = DecisionAction.APPROVE
            reason = "Exact match"
        elif scores["match_confidence"] > 0.70:
            rec = DecisionAction.REVIEW
            reason = "Partial match — possible fee adjustment"
        else:
            rec = DecisionAction.ESCALATE
            reason = "Low match confidence — investigation needed"

        return DecisionOutput(
            recommendation=rec.value,
            recommendation_confidence=scores["match_confidence"],
            recommendation_reason=reason,
            signals_summary=[],
            scores=scores,
        )

    def _evaluate_risk(self, input: DecisionInput) -> DecisionOutput:
        return self._evaluate_generic(input)

    def _evaluate_generic(self, input: DecisionInput) -> DecisionOutput:
        avg_confidence = sum(s.confidence for s in input.signals) / len(input.signals) if input.signals else 0.5

        if avg_confidence >= 0.80:
            rec = DecisionAction.APPROVE
        elif avg_confidence >= 0.50:
            rec = DecisionAction.REVIEW
        else:
            rec = DecisionAction.REJECT

        return DecisionOutput(
            recommendation=rec.value,
            recommendation_confidence=avg_confidence,
            recommendation_reason=f"Generic evaluation: avg confidence {avg_confidence:.2f}",
            signals_summary=[],
            scores={"avg_confidence": avg_confidence},
        )
