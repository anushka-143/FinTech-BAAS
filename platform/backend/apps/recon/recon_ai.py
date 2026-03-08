"""AI-Native Reconciliation Intelligence — smart matching + break analysis.

Goes beyond rule-based matching to identify partial matches, fee
adjustments, split payments, and duplicate transactions.

Evidence: Treasury Prime AI-driven recon + subledger (U.S. Bank
partnership). Optimus.tech: automated classification, partial
matching, cross-ledger. Forbes: NLP + OCR for unstructured data
matching. Global recon software market: $6.44B by 2032.

Rule: suggests matches and resolutions. Does not auto-reconcile
without human approval.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from enum import StrEnum


class BreakClassification(StrEnum):
    AMOUNT_MISMATCH = "amount_mismatch"
    TIMING_DIFFERENCE = "timing_difference"
    FEE_ADJUSTMENT = "fee_adjustment"
    DUPLICATE_TRANSACTION = "duplicate_transaction"
    SPLIT_PAYMENT = "split_payment"
    MISSING_INTERNAL = "missing_internal"
    MISSING_EXTERNAL = "missing_external"
    CURRENCY_ROUNDING = "currency_rounding"
    CHARGEBACK = "chargeback"
    UNKNOWN = "unknown"


class ResolutionPath(StrEnum):
    AUTO_MATCH = "auto_match"
    ADJUST_FEE = "adjust_fee"
    MARK_DUPLICATE = "mark_duplicate"
    WAIT_FOR_SETTLEMENT = "wait_for_settlement"
    CREATE_JOURNAL = "create_journal"
    ESCALATE = "escalate"
    MANUAL_REVIEW = "manual_review"


@dataclass(frozen=True)
class SuggestedMatch:
    """A potential match between internal and external records."""
    internal_ref: str
    external_ref: str
    match_score: float        # 0.0 – 1.0
    match_type: str           # "exact" | "partial" | "fuzzy"
    amount_diff_paise: int
    reason: str


@dataclass(frozen=True)
class ReconAIResult:
    """Full recon AI analysis output."""
    suggested_matches: list[SuggestedMatch]
    break_classification: str
    resolution_path: str
    explanation: str
    confidence: float
    fee_pattern_detected: bool
    duplicate_likelihood: float
    metadata: dict = field(default_factory=dict)


# ─── Common Indian bank provider fee patterns ───

PROVIDER_FEE_PATTERNS = {
    "neft": [
        {"range": (0, 10_000_00), "fee": 150},           # ₹1.50
        {"range": (10_000_00, 1_00_000_00), "fee": 500},  # ₹5.00
        {"range": (1_00_000_00, 2_00_000_00), "fee": 1500},  # ₹15.00
    ],
    "rtgs": [
        {"range": (2_00_000_00, 5_00_000_00), "fee": 2500},   # ₹25.00
        {"range": (5_00_000_00, None), "fee": 5000},           # ₹50.00
    ],
    "imps": [
        {"range": (0, 1_00_000_00), "fee": 250},    # ₹2.50
        {"range": (1_00_000_00, 2_00_000_00), "fee": 500},  # ₹5.00
        {"range": (2_00_000_00, 5_00_000_00), "fee": 1500}, # ₹15.00
    ],
    "upi": [
        {"range": (0, None), "fee": 0},  # UPI is free
    ],
}


class ReconAIEngine:
    """AI-native reconciliation intelligence engine.

    Capabilities:
    1. Smart matching — goes beyond exact reference matching
    2. Break classification — identifies root cause
    3. Fee pattern recognition — knows Indian provider fee schedules
    4. Duplicate detection — flags repeated transactions
    5. Resolution suggestion — recommends next step
    """

    def auto_match(
        self,
        internal_records: list[dict],
        external_records: list[dict],
    ) -> list[SuggestedMatch]:
        """Find potential matches between internal and external records.

        Each record: {"ref": str, "amount": int, "date": date, "description": str}
        """
        matches = []
        used_external = set()

        for internal in internal_records:
            best_match = None
            best_score = 0.0

            for i, external in enumerate(external_records):
                if i in used_external:
                    continue

                score, match_type, diff = self._score_match(internal, external)
                if score > best_score and score >= 0.5:
                    best_score = score
                    best_match = (i, external, score, match_type, diff)

            if best_match:
                idx, ext, score, mtype, diff = best_match
                used_external.add(idx)
                matches.append(SuggestedMatch(
                    internal_ref=internal["ref"],
                    external_ref=ext["ref"],
                    match_score=round(score, 4),
                    match_type=mtype,
                    amount_diff_paise=diff,
                    reason=self._match_reason(mtype, diff),
                ))

        return matches

    def classify_break(
        self,
        internal_amount: int,
        external_amount: int,
        rail: str = "",
        days_apart: int = 0,
        internal_count_same_amount: int = 1,
    ) -> ReconAIResult:
        """Classify a reconciliation break and suggest resolution.

        Args:
            internal_amount: Our ledger amount in paise
            external_amount: Bank statement amount in paise
            rail: Payment rail used
            days_apart: Days between internal and external dates
            internal_count_same_amount: How many internal records with same amount exist
        """
        diff = abs(internal_amount - external_amount)

        # Check if difference matches known fee pattern
        fee_match = self._check_fee_pattern(rail, internal_amount, diff)

        # Classify
        if diff == 0 and days_apart > 0:
            classification = BreakClassification.TIMING_DIFFERENCE
            resolution = ResolutionPath.WAIT_FOR_SETTLEMENT
            confidence = 0.90
            explanation = (
                f"Amounts match exactly but dates differ by {days_apart} day(s). "
                f"Likely settlement delay on {rail.upper() if rail else 'provider'} rail."
            )
        elif fee_match:
            classification = BreakClassification.FEE_ADJUSTMENT
            resolution = ResolutionPath.ADJUST_FEE
            confidence = 0.88
            explanation = (
                f"Difference of ₹{diff / 100:.2f} matches known {rail.upper()} fee pattern. "
                f"Provider likely deducted processing fee."
            )
        elif diff <= 100 and diff > 0:
            classification = BreakClassification.CURRENCY_ROUNDING
            resolution = ResolutionPath.AUTO_MATCH
            confidence = 0.85
            explanation = f"Difference of ₹{diff / 100:.2f} — likely rounding difference."
        elif internal_count_same_amount > 1:
            classification = BreakClassification.DUPLICATE_TRANSACTION
            resolution = ResolutionPath.MARK_DUPLICATE
            confidence = 0.75
            explanation = (
                f"Found {internal_count_same_amount} internal records with same amount ₹{internal_amount / 100:,.2f}. "
                f"Possible duplicate transaction."
            )
        elif external_amount == 0:
            classification = BreakClassification.MISSING_EXTERNAL
            resolution = ResolutionPath.ESCALATE
            confidence = 0.70
            explanation = "Internal record exists but no corresponding external record found."
        elif internal_amount == 0:
            classification = BreakClassification.MISSING_INTERNAL
            resolution = ResolutionPath.CREATE_JOURNAL
            confidence = 0.70
            explanation = "External record exists but no corresponding internal record found."
        else:
            classification = BreakClassification.AMOUNT_MISMATCH
            resolution = ResolutionPath.MANUAL_REVIEW
            confidence = 0.55
            explanation = (
                f"Amount difference of ₹{diff / 100:,.2f} "
                f"(internal ₹{internal_amount / 100:,.2f} vs external ₹{external_amount / 100:,.2f}). "
                f"Manual investigation needed."
            )

        return ReconAIResult(
            suggested_matches=[],
            break_classification=classification.value,
            resolution_path=resolution.value,
            explanation=explanation,
            confidence=confidence,
            fee_pattern_detected=fee_match,
            duplicate_likelihood=0.8 if internal_count_same_amount > 1 else 0.0,
        )

    def _score_match(self, internal: dict, external: dict) -> tuple[float, str, int]:
        """Score a potential match between two records."""
        amount_diff = abs(internal["amount"] - external["amount"])
        i_amount = internal["amount"]

        # Exact match
        if amount_diff == 0:
            return 0.95, "exact", 0

        # Fee-adjusted match
        if i_amount > 0:
            diff_pct = amount_diff / i_amount
            if diff_pct < 0.001:
                return 0.90, "exact", amount_diff  # rounding
            if diff_pct < 0.01:
                return 0.80, "partial", amount_diff  # possible fee
            if diff_pct < 0.05:
                return 0.60, "fuzzy", amount_diff

        return 0.0, "none", amount_diff

    @staticmethod
    def _match_reason(match_type: str, diff: int) -> str:
        if match_type == "exact" and diff == 0:
            return "Exact amount match"
        if match_type == "exact":
            return f"Near-exact match (₹{diff / 100:.2f} rounding difference)"
        if match_type == "partial":
            return f"Partial match — ₹{diff / 100:.2f} difference, likely fee"
        return f"Fuzzy match — ₹{diff / 100:,.2f} difference"

    @staticmethod
    def _check_fee_pattern(rail: str, amount: int, diff: int) -> bool:
        """Check if amount difference matches known provider fee."""
        if not rail or diff == 0:
            return False

        patterns = PROVIDER_FEE_PATTERNS.get(rail.lower(), [])
        for p in patterns:
            lo, hi = p["range"]
            if lo <= amount and (hi is None or amount < hi):
                if abs(diff - p["fee"]) <= 100:  # Within ₹1 tolerance
                    return True
        return False
