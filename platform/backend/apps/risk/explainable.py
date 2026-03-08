"""Explainable Risk Queue Prioritization — human-readable alert intelligence.

Risk alerts are not just scored — they are explained, prioritized, and
presented with actionable narratives for human reviewers.

Evidence: Feedzai "Whitebox Explanations" — analysts understand why a
score or decision was produced. Alloy context-aware AI assistant. Sardine
AI Rule Builder for fraud teams. All confirm: explainability + prioritization
is the standard for 2026 risk platforms.

Rule: explains and prioritizes. Does not clear or freeze on its own.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum


class AlertPriority(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


@dataclass(frozen=True)
class RuleContribution:
    """How much a single rule contributed to the overall score."""
    rule_name: str
    rule_category: str      # "velocity" | "amount" | "behavioral" | "sanctions" | "pattern"
    contribution: float     # 0.0 – 1.0
    detail: str             # Human-readable explanation
    triggered: bool


@dataclass(frozen=True)
class ExplainedAlert:
    """A risk alert with full explainability."""
    alert_id: str
    entity_type: str
    entity_id: str
    priority: str
    priority_rank: int           # 1 = highest priority in queue
    score: float
    explanation_text: str        # Human-readable narrative
    rule_contributions: list[RuleContribution]
    recommended_action: str
    time_to_review_minutes: int  # Recommended time to review
    related_alerts: list[str]    # IDs of potentially related alerts
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class PrioritizedQueue:
    """An ordered queue of explained alerts."""
    alerts: list[ExplainedAlert]
    total_count: int
    critical_count: int
    high_count: int
    generated_at: datetime


class ExplainableRiskEngine:
    """Risk queue prioritization with explainability.

    Scoring formula:
      priority_score = severity_weight * score
                     + recency_weight * recency_factor
                     + amount_weight * amount_factor
                     + history_weight * entity_risk_history
    """

    # Priority weights
    SEVERITY_WEIGHT = 0.40
    RECENCY_WEIGHT = 0.25
    AMOUNT_WEIGHT = 0.20
    HISTORY_WEIGHT = 0.15

    def explain_alert(
        self,
        alert_id: str,
        entity_type: str,
        entity_id: str,
        score: float,
        triggered_rules: list[dict],
        amount_paise: int = 0,
        entity_alert_history_count: int = 0,
    ) -> ExplainedAlert:
        """Generate a human-readable explanation for a risk alert.

        Args:
            alert_id: Alert identifier
            entity_type: "payout" | "beneficiary" | "customer" | "merchant"
            entity_id: Entity identifier
            score: Raw risk score (0.0 – 1.0)
            triggered_rules: List of {"name": str, "category": str, "weight": float, "detail": str}
            amount_paise: Transaction amount if applicable
            entity_alert_history_count: How many past alerts this entity has
        """
        # Build rule contributions
        contributions = []
        for rule in triggered_rules:
            contributions.append(RuleContribution(
                rule_name=rule["name"],
                rule_category=rule.get("category", "general"),
                contribution=rule.get("weight", 0.1),
                detail=rule.get("detail", ""),
                triggered=True,
            ))

        # Determine priority
        priority = self._map_priority(score, entity_alert_history_count)

        # Generate narrative
        narrative = self._generate_narrative(
            entity_type, score, contributions, amount_paise, entity_alert_history_count,
        )

        # Recommended action
        action = self._recommend_action(priority, entity_type, score)

        # Review time estimate
        review_mins = {"critical": 5, "high": 15, "medium": 30, "low": 60}.get(priority, 60)

        return ExplainedAlert(
            alert_id=alert_id,
            entity_type=entity_type,
            entity_id=entity_id,
            priority=priority,
            priority_rank=0,  # Set during queue prioritization
            score=score,
            explanation_text=narrative,
            rule_contributions=contributions,
            recommended_action=action,
            time_to_review_minutes=review_mins,
            related_alerts=[],
        )

    def prioritize_queue(self, alerts: list[ExplainedAlert]) -> PrioritizedQueue:
        """Sort alerts by priority score and assign ranks."""
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "informational": 4}

        sorted_alerts = sorted(
            alerts,
            key=lambda a: (priority_order.get(a.priority, 4), -a.score),
        )

        ranked = []
        for i, alert in enumerate(sorted_alerts):
            ranked.append(ExplainedAlert(
                alert_id=alert.alert_id,
                entity_type=alert.entity_type,
                entity_id=alert.entity_id,
                priority=alert.priority,
                priority_rank=i + 1,
                score=alert.score,
                explanation_text=alert.explanation_text,
                rule_contributions=alert.rule_contributions,
                recommended_action=alert.recommended_action,
                time_to_review_minutes=alert.time_to_review_minutes,
                related_alerts=alert.related_alerts,
            ))

        critical = sum(1 for a in ranked if a.priority == "critical")
        high = sum(1 for a in ranked if a.priority == "high")

        return PrioritizedQueue(
            alerts=ranked,
            total_count=len(ranked),
            critical_count=critical,
            high_count=high,
            generated_at=datetime.now(timezone.utc),
        )

    @staticmethod
    def _map_priority(score: float, history_count: int) -> str:
        if score >= 0.85 or (score >= 0.70 and history_count >= 3):
            return AlertPriority.CRITICAL.value
        if score >= 0.65:
            return AlertPriority.HIGH.value
        if score >= 0.40:
            return AlertPriority.MEDIUM.value
        if score >= 0.20:
            return AlertPriority.LOW.value
        return AlertPriority.INFORMATIONAL.value

    @staticmethod
    def _generate_narrative(
        entity_type: str, score: float,
        contributions: list[RuleContribution],
        amount: int, history: int,
    ) -> str:
        parts = [f"Risk score {score:.0%} for {entity_type}."]

        top_rules = sorted(contributions, key=lambda c: c.contribution, reverse=True)[:3]
        if top_rules:
            rule_details = "; ".join(f"{r.rule_name} ({r.contribution:.0%}): {r.detail}" for r in top_rules)
            parts.append(f"Top contributing factors: {rule_details}.")

        if amount > 0:
            parts.append(f"Transaction amount: ₹{amount / 100:,.2f}.")

        if history > 0:
            parts.append(f"Entity has {history} prior alert(s) — elevated risk history.")

        return " ".join(parts)

    @staticmethod
    def _recommend_action(priority: str, entity_type: str, score: float) -> str:
        if priority == "critical":
            return f"Immediate review required. Consider freezing {entity_type} pending investigation."
        if priority == "high":
            return f"Priority review within 15 minutes. Gather additional context on {entity_type}."
        if priority == "medium":
            return f"Standard review. Check {entity_type} history and related transactions."
        return "Monitor. No immediate action required."
