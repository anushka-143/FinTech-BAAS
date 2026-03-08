"""Payout adapter — our platform's own payout processing.

We handle payout dispatch to Indian banking rails directly:
  UPI:  ≤ ₹1,00,000  — real-time via NPCI
  IMPS: ≤ ₹5,00,000  — real-time via NPCI
  NEFT: ≤ ₹1,00,00,000 — batched (banking hours)
  RTGS: ₹2,00,000 – ₹5,00,00,000 — batched (banking hours)

In sandbox: returns simulated success/failure responses.
In production: dispatches to partner bank APIs.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from packages.core.errors import ValidationError
from packages.providers.base import (
    PayoutProviderAdapter,
    ProviderPayoutRequest,
    ProviderPayoutResponse,
    ProviderPayoutStatus,
)


# ─── Transfer limits in paise (Indian Rupee minor units) ───

RAIL_LIMITS = {
    "upi":  1_00_000_00,       # ₹1,00,000
    "imps": 5_00_000_00,       # ₹5,00,000
    "neft": 1_00_00_000_00,    # ₹1,00,00,000
    "rtgs": 5_00_00_000_00,    # ₹5,00,00,000
}

RTGS_MINIMUM = 2_00_000_00    # ₹2,00,000


class PayoutAdapter(PayoutProviderAdapter):
    """Our platform's payout adapter — connects to Indian banking rails.

    Sandbox mode simulates the full lifecycle:
    - Validation (limits, minimums, required fields)
    - Reference ID generation
    - Realistic response shapes
    """

    async def initiate_payout(self, request: ProviderPayoutRequest) -> ProviderPayoutResponse:
        rail = request.rail.lower()

        # Validate rail-specific requirements
        if rail in ("imps", "neft", "rtgs") and not request.beneficiary_ifsc:
            raise ValidationError(f"{rail.upper()} requires IFSC code")

        if rail == "upi" and not request.beneficiary_vpa:
            raise ValidationError("UPI requires VPA (UPI ID)")

        # Enforce transfer limits
        limit = RAIL_LIMITS.get(rail)
        if limit and request.amount_minor > limit:
            return ProviderPayoutResponse(
                provider_reference="",
                status="rejected",
                raw_status="AMOUNT_EXCEEDS_LIMIT",
                message=f"Amount ₹{request.amount_minor / 100:,.2f} exceeds {rail.upper()} limit of ₹{limit / 100:,.2f}",
            )

        # RTGS minimum check
        if rail == "rtgs" and request.amount_minor < RTGS_MINIMUM:
            return ProviderPayoutResponse(
                provider_reference="",
                status="rejected",
                raw_status="BELOW_RTGS_MINIMUM",
                message=f"RTGS minimum is ₹{RTGS_MINIMUM / 100:,.2f}",
            )

        # Generate reference and simulate successful dispatch
        ref_id = f"PAY-{uuid.uuid4().hex[:12].upper()}"
        utr = f"UTR{uuid.uuid4().hex[:16].upper()}"

        return ProviderPayoutResponse(
            provider_reference=ref_id,
            status="pending" if rail in ("neft", "rtgs") else "accepted",
            raw_status="INITIATED",
            message=f"Payout dispatched via {rail.upper()}",
            raw_response={
                "transaction_id": ref_id,
                "utr": utr,
                "rail": rail,
                "bank_reference": f"BNK{uuid.uuid4().hex[:10].upper()}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

    async def get_payout_status(self, provider_reference: str) -> ProviderPayoutStatus:
        # Sandbox: return success for any reference
        return ProviderPayoutStatus(
            provider_reference=provider_reference,
            status="success",
            raw_status="COMPLETED",
            utr=f"UTR{uuid.uuid4().hex[:16].upper()}",
            completed_at=datetime.now(timezone.utc),
        )
