"""Risk Feature Pipeline — online and offline features for risk scoring.

Computes real-time and batch features:
  - Velocity features (transaction count/volume in time windows)
  - Behavioral features (time-of-day patterns, device fingerprint)
  - Beneficiary history features
  - Account-level aggregates
  - Anomaly indicators

Features are computed from live DB and cached for fast serving.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class RiskFeatures:
    """Computed risk features for a transaction/entity."""
    entity_id: str
    entity_type: str  # "beneficiary" | "payer" | "tenant"
    computed_at: datetime

    # Velocity features
    txn_count_1h: int = 0
    txn_count_24h: int = 0
    txn_count_7d: int = 0
    txn_volume_1h_paise: int = 0
    txn_volume_24h_paise: int = 0
    txn_volume_7d_paise: int = 0

    # Behavioral features
    avg_txn_amount_paise: int = 0
    max_txn_amount_paise: int = 0
    unique_beneficiaries_24h: int = 0
    is_off_hours: bool = False  # Transaction outside 8AM-8PM IST

    # History features
    account_age_days: int = 0
    first_seen: datetime | None = None
    total_lifetime_txns: int = 0

    # Anomaly indicators
    amount_zscore: float = 0.0  # How many std devs from mean
    velocity_spike: bool = False  # Sudden increase in txn rate
    new_beneficiary: bool = False  # First-time beneficiary

    # Composite risk signal
    risk_signal: float = 0.0  # 0.0 (safe) to 1.0 (risky)


class FeaturePipeline:
    """Computes risk features from live database.

    Usage:
        pipeline = FeaturePipeline()
        features = await pipeline.compute_payout_features(
            tenant_id="...", beneficiary_id="...", amount_paise=100000,
        )
    """

    async def compute_payout_features(
        self,
        tenant_id: str,
        beneficiary_id: str | None = None,
        amount_paise: int = 0,
        payer_id: str | None = None,
    ) -> RiskFeatures:
        """Compute real-time features for a payout transaction."""
        now = datetime.now(timezone.utc)
        features = RiskFeatures(
            entity_id=beneficiary_id or tenant_id,
            entity_type="beneficiary" if beneficiary_id else "tenant",
            computed_at=now,
        )

        try:
            from packages.db.engine import get_session_factory
            from packages.schemas.payouts import PayoutRequest

            factory = get_session_factory()
            async with factory() as session:
                tid = uuid.UUID(tenant_id)

                # ─── Velocity features ───
                for window_name, hours in [("1h", 1), ("24h", 24), ("7d", 168)]:
                    cutoff = now - timedelta(hours=hours)
                    stmt = select(
                        func.count(PayoutRequest.id),
                        func.coalesce(func.sum(PayoutRequest.amount), 0),
                    ).where(and_(
                        PayoutRequest.tenant_id == tid,
                        PayoutRequest.created_at >= cutoff,
                    ))
                    if beneficiary_id:
                        stmt = stmt.where(PayoutRequest.beneficiary_id == uuid.UUID(beneficiary_id))

                    result = await session.execute(stmt)
                    row = result.one()
                    count, volume = int(row[0]), int(row[1])

                    setattr(features, f"txn_count_{window_name}", count)
                    setattr(features, f"txn_volume_{window_name}_paise", volume)

                # ─── Behavioral features ───
                if features.txn_count_7d > 0:
                    stmt_avg = select(
                        func.avg(PayoutRequest.amount),
                        func.max(PayoutRequest.amount),
                    ).where(and_(
                        PayoutRequest.tenant_id == tid,
                        PayoutRequest.created_at >= now - timedelta(days=30),
                    ))
                    result = await session.execute(stmt_avg)
                    row = result.one()
                    features.avg_txn_amount_paise = int(row[0] or 0)
                    features.max_txn_amount_paise = int(row[1] or 0)

                # Unique beneficiaries in 24h
                stmt_uniq = select(
                    func.count(func.distinct(PayoutRequest.beneficiary_id))
                ).where(and_(
                    PayoutRequest.tenant_id == tid,
                    PayoutRequest.created_at >= now - timedelta(hours=24),
                ))
                result = await session.execute(stmt_uniq)
                features.unique_beneficiaries_24h = int(result.scalar() or 0)

                # Off-hours check (IST: UTC+5:30)
                ist_hour = (now.hour + 5) % 24
                features.is_off_hours = ist_hour < 8 or ist_hour > 20

                # ─── History features ───
                if beneficiary_id:
                    stmt_first = select(
                        func.min(PayoutRequest.created_at),
                        func.count(PayoutRequest.id),
                    ).where(and_(
                        PayoutRequest.tenant_id == tid,
                        PayoutRequest.beneficiary_id == uuid.UUID(beneficiary_id),
                    ))
                    result = await session.execute(stmt_first)
                    row = result.one()
                    if row[0]:
                        features.first_seen = row[0]
                        features.account_age_days = (now - row[0]).days
                        features.total_lifetime_txns = int(row[1])
                        features.new_beneficiary = features.total_lifetime_txns <= 1

                # ─── Anomaly indicators ───
                if features.avg_txn_amount_paise > 0 and amount_paise > 0:
                    # Simple z-score approximation
                    if features.max_txn_amount_paise > features.avg_txn_amount_paise:
                        std_approx = (features.max_txn_amount_paise - features.avg_txn_amount_paise) / 2
                        if std_approx > 0:
                            features.amount_zscore = round(
                                (amount_paise - features.avg_txn_amount_paise) / std_approx, 2
                            )

                # Velocity spike: 1h count > 50% of 24h count
                if features.txn_count_24h > 5:
                    features.velocity_spike = features.txn_count_1h > features.txn_count_24h * 0.5

        except Exception:
            pass  # Return default features on DB error

        # ─── Composite risk signal ───
        features.risk_signal = self._compute_risk_signal(features, amount_paise)

        return features

    @staticmethod
    def _compute_risk_signal(f: RiskFeatures, amount_paise: int) -> float:
        """Compute composite risk signal from features."""
        score = 0.0

        # Velocity-based risk
        if f.velocity_spike:
            score += 0.25
        if f.txn_count_1h > 20:
            score += 0.15

        # Amount-based risk
        if f.amount_zscore > 3.0:
            score += 0.20
        elif f.amount_zscore > 2.0:
            score += 0.10

        # Behavioral risk
        if f.is_off_hours:
            score += 0.05
        if f.new_beneficiary:
            score += 0.10
        if f.unique_beneficiaries_24h > 10:
            score += 0.10

        # Account age risk
        if f.account_age_days < 7:
            score += 0.10
        elif f.account_age_days < 30:
            score += 0.05

        return min(1.0, round(score, 4))
