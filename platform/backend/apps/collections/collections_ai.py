"""AI Collections Intelligence — prioritization, prediction, follow-up.

Evidence: Decentro AI-enhanced collections and hybrid AI+human servicing
models. This is a later-phase feature but fits the platform architecture.

Capabilities:
  1. Collection prioritization — rank outstanding by urgency
  2. Payment prediction — likelihood and timing of expected payments
  3. Follow-up intelligence — optimal channel, time, and message
  4. Aging analysis — bucket outstanding by age + risk

Rule: recommends actions and timing. Does not execute collection
actions or send customer communications directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from enum import StrEnum


class CollectionUrgency(StrEnum):
    CRITICAL = "critical"    # 90+ days, high amount
    HIGH = "high"            # 60-90 days or high amount
    MEDIUM = "medium"        # 30-60 days
    LOW = "low"              # < 30 days
    ON_TRACK = "on_track"    # Not yet due


class FollowUpChannel(StrEnum):
    SMS = "sms"
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    PHONE_CALL = "phone_call"
    IN_APP = "in_app"


@dataclass(frozen=True)
class CollectionInsight:
    """AI-generated insight for a single outstanding collection."""
    collection_id: str
    amount_paise: int
    days_overdue: int
    priority_score: float           # 0.0 – 1.0
    urgency: str
    predicted_payment_date: date | None
    payment_likelihood: float       # 0.0 – 1.0
    suggested_action: str
    suggested_channel: str
    optimal_contact_time: str       # e.g., "10:00-12:00 IST"
    risk_of_default: float          # 0.0 – 1.0


@dataclass(frozen=True)
class AgingBucket:
    """Collections aging bucket."""
    bucket: str                     # "current" | "1-30" | "31-60" | "61-90" | "90+"
    count: int
    total_amount_paise: int
    avg_payment_likelihood: float


@dataclass(frozen=True)
class CollectionsDashboard:
    """AI-generated collections intelligence summary."""
    total_outstanding_paise: int
    total_count: int
    aging_buckets: list[AgingBucket]
    top_priorities: list[CollectionInsight]
    predicted_recovery_rate: float
    generated_at: datetime


class CollectionsAIEngine:
    """AI-powered collections intelligence.

    Uses payment history patterns, aging analysis, and behavioral
    signals to prioritize collections and predict outcomes.
    """

    def analyze_collection(
        self,
        collection_id: str,
        amount_paise: int,
        due_date: date,
        customer_payment_history: list[dict] | None = None,
        customer_risk_score: float = 0.0,
    ) -> CollectionInsight:
        """Generate AI insight for a single collection.

        Args:
            collection_id: Collection identifier
            amount_paise: Outstanding amount in paise
            due_date: Original due date
            customer_payment_history: [{"paid_on_time": bool, "days_late": int}]
            customer_risk_score: Customer's risk score (0.0 – 1.0)
        """
        today = date.today()
        days_overdue = max(0, (today - due_date).days)
        history = customer_payment_history or []

        # Calculate priority score
        priority = self._calculate_priority(amount_paise, days_overdue, customer_risk_score)
        urgency = self._map_urgency(days_overdue, amount_paise)

        # Predict payment
        likelihood = self._predict_payment_likelihood(days_overdue, history, customer_risk_score)
        predicted_date = self._predict_payment_date(days_overdue, history, today)

        # Suggest action
        action = self._suggest_action(days_overdue, likelihood, amount_paise)
        channel = self._suggest_channel(days_overdue, amount_paise)
        contact_time = self._suggest_contact_time(history)

        # Default risk
        default_risk = min(1.0, customer_risk_score * 0.4 + (days_overdue / 180) * 0.6)

        return CollectionInsight(
            collection_id=collection_id,
            amount_paise=amount_paise,
            days_overdue=days_overdue,
            priority_score=round(priority, 4),
            urgency=urgency,
            predicted_payment_date=predicted_date,
            payment_likelihood=round(likelihood, 4),
            suggested_action=action,
            suggested_channel=channel,
            optimal_contact_time=contact_time,
            risk_of_default=round(default_risk, 4),
        )

    def generate_dashboard(
        self,
        collections: list[CollectionInsight],
    ) -> CollectionsDashboard:
        """Generate collections intelligence dashboard."""
        if not collections:
            return CollectionsDashboard(
                total_outstanding_paise=0, total_count=0,
                aging_buckets=[], top_priorities=[],
                predicted_recovery_rate=0.0,
                generated_at=datetime.now(timezone.utc),
            )

        total = sum(c.amount_paise for c in collections)
        buckets = self._compute_aging_buckets(collections)
        top = sorted(collections, key=lambda c: c.priority_score, reverse=True)[:10]
        avg_likelihood = sum(c.payment_likelihood for c in collections) / len(collections)

        return CollectionsDashboard(
            total_outstanding_paise=total,
            total_count=len(collections),
            aging_buckets=buckets,
            top_priorities=top,
            predicted_recovery_rate=round(avg_likelihood, 4),
            generated_at=datetime.now(timezone.utc),
        )

    @staticmethod
    def _calculate_priority(amount: int, days_overdue: int, risk_score: float) -> float:
        amount_factor = min(1.0, amount / 10_00_000_00)  # Normalize to ₹10L
        age_factor = min(1.0, days_overdue / 90)
        risk_factor = risk_score
        return 0.35 * age_factor + 0.35 * amount_factor + 0.30 * risk_factor

    @staticmethod
    def _map_urgency(days_overdue: int, amount: int) -> str:
        if days_overdue >= 90 or (days_overdue >= 60 and amount > 5_00_000_00):
            return CollectionUrgency.CRITICAL.value
        if days_overdue >= 60 or amount > 10_00_000_00:
            return CollectionUrgency.HIGH.value
        if days_overdue >= 30:
            return CollectionUrgency.MEDIUM.value
        if days_overdue > 0:
            return CollectionUrgency.LOW.value
        return CollectionUrgency.ON_TRACK.value

    @staticmethod
    def _predict_payment_likelihood(days_overdue: int, history: list[dict], risk: float) -> float:
        base = max(0.1, 1.0 - (days_overdue / 120))
        if history:
            on_time_rate = sum(1 for h in history if h.get("paid_on_time", False)) / len(history)
            base = base * 0.6 + on_time_rate * 0.4
        return base * (1 - risk * 0.3)

    @staticmethod
    def _predict_payment_date(days_overdue: int, history: list[dict], today: date) -> date | None:
        if days_overdue > 120:
            return None  # Unlikely to pay
        avg_late = 7
        if history:
            late_days = [h.get("days_late", 0) for h in history if h.get("days_late", 0) > 0]
            if late_days:
                avg_late = sum(late_days) // len(late_days)
        return today + timedelta(days=max(1, avg_late))

    @staticmethod
    def _suggest_action(days_overdue: int, likelihood: float, amount: int) -> str:
        if days_overdue == 0:
            return "No action needed — payment not yet due"
        if days_overdue <= 7:
            return "Send gentle payment reminder"
        if days_overdue <= 30:
            return "Send firm follow-up with payment link"
        if days_overdue <= 60:
            return "Escalate to collections team for direct outreach"
        if days_overdue <= 90:
            return "Initiate formal collection notice"
        return "Consider legal/recovery proceedings"

    @staticmethod
    def _suggest_channel(days_overdue: int, amount: int) -> str:
        if days_overdue <= 7:
            return FollowUpChannel.SMS.value
        if days_overdue <= 30:
            return FollowUpChannel.WHATSAPP.value
        if days_overdue <= 60:
            return FollowUpChannel.EMAIL.value
        return FollowUpChannel.PHONE_CALL.value

    @staticmethod
    def _suggest_contact_time(history: list[dict]) -> str:
        # Default: Indian business hours
        return "10:00-12:00 IST"

    @staticmethod
    def _compute_aging_buckets(collections: list[CollectionInsight]) -> list[AgingBucket]:
        buckets_def = [
            ("current", 0, 0),
            ("1-30", 1, 30),
            ("31-60", 31, 60),
            ("61-90", 61, 90),
            ("90+", 91, 999999),
        ]
        result = []
        for name, lo, hi in buckets_def:
            in_bucket = [c for c in collections if lo <= c.days_overdue <= hi]
            if in_bucket or name in ("current", "1-30"):
                avg_lik = sum(c.payment_likelihood for c in in_bucket) / max(len(in_bucket), 1)
                result.append(AgingBucket(
                    bucket=name,
                    count=len(in_bucket),
                    total_amount_paise=sum(c.amount_paise for c in in_bucket),
                    avg_payment_likelihood=round(avg_lik, 4),
                ))
        return result
