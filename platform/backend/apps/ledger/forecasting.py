"""Cashflow Forecasting — AI-powered inflow/outflow prediction.

Uses historical ledger journal data to predict future cash positions.
Direct method: analyzes actual inflows and outflows by day.

Evidence: JP Morgan, HighRadius, Forbes — LSTM/Prophet models achieve
30-50% accuracy improvement. Cash flow forecast market $726M in 2025,
$1.68B in 2026. Python ecosystem: Prophet, statsmodels, scikit-learn.

In sandbox: uses statistical pattern detection (moving averages,
day-of-week seasonality, trend detection).
In production: can integrate Prophet/LSTM models.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from enum import StrEnum


class ForecastPeriod(StrEnum):
    WEEK = "7d"
    TWO_WEEKS = "14d"
    MONTH = "30d"
    QUARTER = "90d"


@dataclass(frozen=True)
class DailyPrediction:
    """Single day forecast."""
    date: date
    predicted_inflow: int     # in paise
    predicted_outflow: int    # in paise
    predicted_net: int        # in paise
    upper_bound: int          # optimistic (in paise)
    lower_bound: int          # pessimistic (in paise)
    confidence: float         # 0.0 – 1.0 (decays with horizon)


@dataclass(frozen=True)
class CashflowAnomaly:
    """Detected anomaly in cash flow patterns."""
    date: date
    anomaly_type: str         # "unusual_outflow" | "missing_inflow" | "spike"
    description: str
    severity: str             # "low" | "medium" | "high"


@dataclass(frozen=True)
class ForecastResult:
    """Complete forecast output."""
    tenant_id: str
    account_id: str | None
    period: str
    predictions: list[DailyPrediction]
    current_balance: int
    predicted_end_balance: int
    trend: str                    # "growing" | "declining" | "stable"
    seasonality_detected: bool
    anomalies: list[CashflowAnomaly]
    confidence_overall: float
    generated_at: datetime
    metadata: dict = field(default_factory=dict)


class CashflowForecaster:
    """AI-powered cashflow forecasting engine.

    Pipeline:
    1. Aggregate historical daily flows from ledger
    2. Detect seasonality (day-of-week, day-of-month)
    3. Calculate trend (moving average slope)
    4. Generate predictions with confidence bounds
    5. Flag anomalies

    In sandbox: uses statistical methods (SMA, seasonality indices).
    In production: use Prophet or LSTM for better accuracy.
    """

    def forecast(
        self,
        tenant_id: str,
        historical_daily_flows: list[dict],  # [{"date": date, "inflow": int, "outflow": int}]
        period: ForecastPeriod = ForecastPeriod.MONTH,
        current_balance: int = 0,
        account_id: str | None = None,
    ) -> ForecastResult:
        """Generate a cashflow forecast from historical data.

        Args:
            tenant_id: Tenant identifier
            historical_daily_flows: At least 14 days of history recommended
            period: Forecast horizon
            current_balance: Current balance in paise
            account_id: Optional specific account to forecast
        """
        days = int(period.value.replace("d", ""))
        now = datetime.now(timezone.utc)

        if len(historical_daily_flows) < 7:
            # Insufficient data — return flat forecast
            return self._flat_forecast(
                tenant_id, account_id, period, current_balance, days, now,
            )

        # Extract time series
        inflows = [d["inflow"] for d in historical_daily_flows]
        outflows = [d["outflow"] for d in historical_daily_flows]
        nets = [d["inflow"] - d["outflow"] for d in historical_daily_flows]
        dates = [d["date"] for d in historical_daily_flows]

        # Detect seasonality (day-of-week patterns)
        dow_inflow = self._day_of_week_seasonality(dates, inflows)
        dow_outflow = self._day_of_week_seasonality(dates, outflows)

        # Compute trend
        trend_slope = self._trend_slope(nets)
        trend = "growing" if trend_slope > 0.02 else ("declining" if trend_slope < -0.02 else "stable")

        # Base predictions (moving average + seasonality + trend)
        avg_inflow = statistics.mean(inflows) if inflows else 0
        avg_outflow = statistics.mean(outflows) if outflows else 0
        std_inflow = statistics.stdev(inflows) if len(inflows) > 1 else avg_inflow * 0.2
        std_outflow = statistics.stdev(outflows) if len(outflows) > 1 else avg_outflow * 0.2

        last_date = dates[-1] if dates else now.date()
        predictions = []
        running_balance = current_balance

        for i in range(1, days + 1):
            pred_date = last_date + timedelta(days=i)
            dow = pred_date.weekday()

            # Apply seasonality multiplier
            seasonal_in = dow_inflow.get(dow, 1.0)
            seasonal_out = dow_outflow.get(dow, 1.0)

            # Apply trend
            trend_factor = 1.0 + (trend_slope * i / days)

            pred_in = int(avg_inflow * seasonal_in * trend_factor)
            pred_out = int(avg_outflow * seasonal_out * trend_factor)
            pred_net = pred_in - pred_out

            # Confidence decays with horizon
            confidence = max(0.3, 1.0 - (i / days) * 0.5)

            # Bounds (1 std deviation scaled by confidence)
            bound_margin = int((std_inflow + std_outflow) * (1 - confidence + 0.5))
            upper = pred_net + bound_margin
            lower = pred_net - bound_margin

            running_balance += pred_net

            predictions.append(DailyPrediction(
                date=pred_date,
                predicted_inflow=pred_in,
                predicted_outflow=pred_out,
                predicted_net=pred_net,
                upper_bound=upper,
                lower_bound=lower,
                confidence=round(confidence, 3),
            ))

        # Detect anomalies in historical data
        anomalies = self._detect_anomalies(dates, inflows, outflows, avg_inflow, avg_outflow, std_inflow, std_outflow)

        avg_confidence = statistics.mean([p.confidence for p in predictions]) if predictions else 0.0

        return ForecastResult(
            tenant_id=tenant_id,
            account_id=account_id,
            period=period.value,
            predictions=predictions,
            current_balance=current_balance,
            predicted_end_balance=running_balance,
            trend=trend,
            seasonality_detected=bool(dow_inflow),
            anomalies=anomalies,
            confidence_overall=round(avg_confidence, 3),
            generated_at=now,
        )

    @staticmethod
    def _day_of_week_seasonality(dates: list[date], values: list[int]) -> dict[int, float]:
        """Compute day-of-week seasonality indices."""
        if not dates or not values:
            return {}

        dow_sums: dict[int, list[int]] = {i: [] for i in range(7)}
        for d, v in zip(dates, values):
            dow_sums[d.weekday()].append(v)

        overall_avg = statistics.mean(values) if values else 1
        if overall_avg == 0:
            return {}

        return {
            dow: (statistics.mean(vals) / overall_avg) if vals else 1.0
            for dow, vals in dow_sums.items()
        }

    @staticmethod
    def _trend_slope(values: list[int]) -> float:
        """Simple linear trend slope (normalized)."""
        if len(values) < 3:
            return 0.0
        n = len(values)
        x_mean = (n - 1) / 2
        y_mean = statistics.mean(values)
        if y_mean == 0:
            return 0.0

        numerator = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
        denominator = sum((i - x_mean) ** 2 for i in range(n))

        if denominator == 0:
            return 0.0
        slope = numerator / denominator
        return slope / abs(y_mean)  # Normalize

    @staticmethod
    def _detect_anomalies(
        dates: list[date], inflows: list[int], outflows: list[int],
        avg_in: float, avg_out: float, std_in: float, std_out: float,
    ) -> list[CashflowAnomaly]:
        anomalies = []
        threshold = 2.0  # 2 standard deviations

        for d, inf, outf in zip(dates, inflows, outflows):
            if std_in > 0 and inf > avg_in + threshold * std_in:
                anomalies.append(CashflowAnomaly(
                    date=d, anomaly_type="spike",
                    description=f"Unusual inflow spike: ₹{inf / 100:,.0f} vs avg ₹{avg_in / 100:,.0f}",
                    severity="medium",
                ))
            if std_out > 0 and outf > avg_out + threshold * std_out:
                anomalies.append(CashflowAnomaly(
                    date=d, anomaly_type="unusual_outflow",
                    description=f"Unusual outflow: ₹{outf / 100:,.0f} vs avg ₹{avg_out / 100:,.0f}",
                    severity="high",
                ))

        return anomalies[:10]  # Cap at 10 most recent

    @staticmethod
    def _flat_forecast(
        tenant_id: str, account_id: str | None, period: str,
        balance: int, days: int, now: datetime,
    ) -> ForecastResult:
        """Flat forecast when insufficient historical data."""
        predictions = [
            DailyPrediction(
                date=now.date() + timedelta(days=i + 1),
                predicted_inflow=0, predicted_outflow=0, predicted_net=0,
                upper_bound=0, lower_bound=0, confidence=0.1,
            )
            for i in range(days)
        ]
        return ForecastResult(
            tenant_id=tenant_id, account_id=account_id,
            period=period, predictions=predictions,
            current_balance=balance, predicted_end_balance=balance,
            trend="stable", seasonality_detected=False,
            anomalies=[], confidence_overall=0.1,
            generated_at=now,
            metadata={"warning": "Insufficient historical data for accurate forecast"},
        )
