"""AI Router Engine — deterministic first, LLM only for exceptions.

The audit identified that routing every AI task through the full LLM
pipeline (Gemini 2.5 Pro) will destroy SaaS gross margins and introduce latency.

This engine implements a two-tier routing strategy:
  Tier 1: Cheap deterministic services (pattern matching, rules, scoring)
  Tier 2: Expensive LLM orchestration (only when deterministic confidence < threshold)

Example cost comparison (per 1000 tasks):
  - Full LLM: ~$15-40 in API costs + 2-5s latency per call
  - Deterministic first: ~$0.50 (90% handled by rules) + <50ms per call

The router checks if a cheaper handler can resolve the task with
sufficient confidence before escalating to the AI orchestrator.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class CostTier(StrEnum):
    DETERMINISTIC = "deterministic"   # Free, <50ms
    LIGHTWEIGHT_ML = "lightweight_ml"  # Cheap, <200ms
    FULL_LLM = "full_llm"            # Expensive, 2-5s


@dataclass(frozen=True)
class RoutingResult:
    """Output from the AI Router — includes cost tracking."""
    used_llm: bool
    cost_tier: str
    confidence: float
    result: Any  # AIAnalysisResult or deterministic equivalent
    deterministic_attempted: bool
    escalation_reason: str | None


# Minimum confidence for deterministic to be accepted (no LLM needed)
DETERMINISTIC_CONFIDENCE_THRESHOLD = 0.75


class AIRouterEngine:
    """Routes AI tasks to the cheapest handler that can resolve them.

    Strategy per task type:
      PAYOUT_TRIAGE → smart_routing classification first
      RECON_ANALYSIS → recon_ai classification first
      RISK_EXPLANATION → explainable risk engine first
      KYC_REVIEW → extraction confidence check first
      TRANSACTION_CATEGORIZATION → pattern matcher first
      OPS_COPILOT → always LLM (needs natural language)
      DEVELOPER_COPILOT → always LLM (needs natural language)
    """

    def route(self, task_type: str, context: dict[str, Any]) -> RoutingResult:
        """Try deterministic handler first, escalate to LLM if needed."""

        handler = self._deterministic_handlers.get(task_type)
        if handler is None:
            return RoutingResult(
                used_llm=True,
                cost_tier=CostTier.FULL_LLM.value,
                confidence=0.0,
                result=None,  # Caller should invoke orchestrator
                deterministic_attempted=False,
                escalation_reason=f"No deterministic handler for {task_type}",
            )

        try:
            result, confidence = handler(context)
        except Exception:
            return RoutingResult(
                used_llm=True,
                cost_tier=CostTier.FULL_LLM.value,
                confidence=0.0,
                result=None,
                deterministic_attempted=True,
                escalation_reason="Deterministic handler raised an exception",
            )

        if confidence >= DETERMINISTIC_CONFIDENCE_THRESHOLD:
            return RoutingResult(
                used_llm=False,
                cost_tier=CostTier.DETERMINISTIC.value,
                confidence=confidence,
                result=result,
                deterministic_attempted=True,
                escalation_reason=None,
            )

        return RoutingResult(
            used_llm=True,
            cost_tier=CostTier.FULL_LLM.value,
            confidence=confidence,
            result=None,
            deterministic_attempted=True,
            escalation_reason=f"Deterministic confidence {confidence:.0%} below threshold {DETERMINISTIC_CONFIDENCE_THRESHOLD:.0%}",
        )

    @property
    def _deterministic_handlers(self) -> dict:
        return {
            "payout_triage": self._deterministic_payout_triage,
            "recon_analysis": self._deterministic_recon_analysis,
            "risk_explanation": self._deterministic_risk_explanation,
            "kyc_review": self._deterministic_kyc_review,
        }

    @staticmethod
    def _deterministic_payout_triage(ctx: dict) -> tuple[dict, float]:
        """Classify payout failure using deterministic rules."""
        error = ctx.get("error_message", "").lower()
        rail = ctx.get("rail", "")

        # High-confidence classification patterns
        classifications = {
            "insufficient": ("insufficient_funds", "Release hold, notify tenant", 0.95),
            "invalid ifsc": ("invalid_beneficiary", "Verify IFSC with NPCI directory", 0.92),
            "invalid account": ("invalid_beneficiary", "Re-verify account number", 0.92),
            "account closed": ("invalid_beneficiary", "Mark beneficiary inactive", 0.90),
            "timeout": ("provider_timeout", f"Retry on {rail} after 60s", 0.85),
            "rate limit": ("provider_throttled", "Backoff and retry in 5 minutes", 0.88),
            "maintenance": ("provider_downtime", "Queue for retry, switch rail if urgent", 0.90),
            "duplicate": ("duplicate_request", "Check idempotency key, do not retry", 0.95),
            "beneficiary bank": ("beneficiary_bank_issue", "Try alternate rail", 0.80),
            "neft window": ("outside_banking_hours", "Queue for next NEFT batch", 0.95),
        }

        for keyword, (category, action, confidence) in classifications.items():
            if keyword in error:
                return {
                    "category": category,
                    "action": action,
                    "is_retryable": category in ("provider_timeout", "provider_throttled", "provider_downtime"),
                    "confidence": confidence,
                }, confidence

        # Low confidence — needs LLM
        return {"category": "unknown", "action": "Escalate to AI"}, 0.30

    @staticmethod
    def _deterministic_recon_analysis(ctx: dict) -> tuple[dict, float]:
        """Classify recon break using deterministic patterns."""
        from apps.recon.recon_ai import ReconAIEngine
        engine = ReconAIEngine()
        result = engine.classify_break(
            internal_amount=ctx.get("internal_amount", 0),
            external_amount=ctx.get("external_amount", 0),
            rail=ctx.get("rail", ""),
            days_apart=ctx.get("days_apart", 0),
            internal_count_same_amount=ctx.get("duplicate_count", 1),
        )
        return {
            "classification": result.break_classification,
            "resolution": result.resolution_path,
            "explanation": result.explanation,
        }, result.confidence

    @staticmethod
    def _deterministic_risk_explanation(ctx: dict) -> tuple[dict, float]:
        """Generate risk explanation using deterministic engine."""
        from apps.risk.explainable import ExplainableRiskEngine
        engine = ExplainableRiskEngine()
        alert = engine.explain_alert(
            alert_id=ctx.get("alert_id", ""),
            entity_type=ctx.get("entity_type", ""),
            entity_id=ctx.get("entity_id", ""),
            score=ctx.get("score", 0.0),
            triggered_rules=ctx.get("triggered_rules", []),
            amount_paise=ctx.get("amount_paise", 0),
            entity_alert_history_count=ctx.get("history_count", 0),
        )
        return {
            "priority": alert.priority,
            "explanation": alert.explanation_text,
            "action": alert.recommended_action,
            "contributions": [
                {"rule": c.rule_name, "weight": c.contribution}
                for c in alert.rule_contributions
            ],
        }, 0.85  # Deterministic explanations are always reliable

    @staticmethod
    def _deterministic_kyc_review(ctx: dict) -> tuple[dict, float]:
        """Quick KYC review using extraction confidence scores."""
        fields = ctx.get("extraction_fields", [])
        if not fields:
            return {"status": "needs_llm"}, 0.20

        avg_confidence = sum(f.get("confidence", 0) for f in fields) / len(fields)
        low_confidence_fields = [f for f in fields if f.get("confidence", 0) < 0.7]
        mismatches = ctx.get("mismatches", [])

        if avg_confidence > 0.90 and not low_confidence_fields and not mismatches:
            return {
                "recommendation": "approve",
                "reason": f"All {len(fields)} fields extracted with avg confidence {avg_confidence:.0%}. No mismatches.",
                "risk_level": "low",
            }, 0.88

        if mismatches:
            return {
                "recommendation": "review",
                "reason": f"Found {len(mismatches)} mismatch(es): {', '.join(mismatches)}",
                "risk_level": "medium",
            }, 0.82

        # Borderline — needs LLM
        return {
            "recommendation": "needs_deeper_review",
            "reason": f"Avg confidence {avg_confidence:.0%}, {len(low_confidence_fields)} low-confidence fields",
        }, 0.55
