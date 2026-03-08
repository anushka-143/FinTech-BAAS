"""AI Transaction Categorization — auto-classify payments by type.

Uses NLP pattern matching on narration text, merchant codes (MCC),
and UPI VPA patterns to categorize transactions into India-specific
categories.

Evidence: Plaid AI-enhanced categorization uses AI-assisted label
generation + human review. BERT/NLP for merchant name parsing.
This is already productized in adjacent fintech infrastructure.

India-specific categories aligned with GST, ITR, and bank statement
analysis requirements.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum


class TransactionCategory(StrEnum):
    SALARY = "salary"
    VENDOR_PAYMENT = "vendor_payment"
    REFUND = "refund"
    SUBSCRIPTION = "subscription"
    EMI = "emi"
    RENT = "rent"
    UTILITY = "utility"
    GOVERNMENT = "government"
    UPI_P2P = "upi_p2p"
    INVESTMENT = "investment"
    INSURANCE = "insurance"
    LOAN_DISBURSEMENT = "loan_disbursement"
    LOAN_REPAYMENT = "loan_repayment"
    TAX_PAYMENT = "tax_payment"
    FOOD_DINING = "food_dining"
    TRAVEL = "travel"
    SHOPPING = "shopping"
    HEALTHCARE = "healthcare"
    EDUCATION = "education"
    TRANSFER = "transfer"
    OTHER = "other"


@dataclass(frozen=True)
class CategoryResult:
    """Output from the categorization engine."""
    primary: str
    subcategory: str | None
    confidence: float
    merchant_name: str | None
    mcc: str | None
    method: str  # "pattern" | "mcc" | "vpa" | "narration_nlp"


# ─── Pattern rules (India-specific) ───

NARRATION_PATTERNS: list[tuple[str, str, str | None]] = [
    # (regex pattern, category, subcategory)
    (r"(?i)salary|payroll|wages|stipend", "salary", None),
    (r"(?i)emi\b|equated monthly|loan repay", "emi", None),
    (r"(?i)rent\b|house rent|rental", "rent", None),
    (r"(?i)refund|reversal|cashback|return", "refund", None),
    (r"(?i)subscription|netflix|hotstar|spotify|amazon prime|youtube premium", "subscription", "entertainment"),
    (r"(?i)electricity|water bill|gas bill|broadband|wifi|airtel|jio|bsnl|vodafone", "utility", None),
    (r"(?i)gst|tds|income tax|advance tax|challan|nsdl|tin-nsdl", "tax_payment", None),
    (r"(?i)lic|insurance|health insurance|motor insurance|policy premium", "insurance", None),
    (r"(?i)mutual fund|sip|demat|zerodha|groww|upstox|smallcase|nifty", "investment", "mutual_fund"),
    (r"(?i)fd|fixed deposit|recurring deposit|rd\b", "investment", "deposit"),
    (r"(?i)swiggy|zomato|dominos|mcdonalds|starbucks|cafe|restaurant|food", "food_dining", None),
    (r"(?i)irctc|makemytrip|goibibo|ola|uber|rapido|flight|hotel|travel", "travel", None),
    (r"(?i)amazon|flipkart|myntra|ajio|nykaa|shopping|purchase", "shopping", "online"),
    (r"(?i)hospital|clinic|pharmacy|apollo|medplus|doctor|medical", "healthcare", None),
    (r"(?i)school|college|university|tuition|exam fee|education", "education", None),
    (r"(?i)loan disburs|credit line|overdraft", "loan_disbursement", None),
    (r"(?i)neft|rtgs|imps|transfer|fund transfer", "transfer", None),
    (r"(?i)govt|government|pension|subsidy|dbt|pm kisan", "government", None),
]

# UPI VPA patterns for merchant identification
VPA_MERCHANT_PATTERNS: list[tuple[str, str, str | None]] = [
    (r"(?i)swiggy", "food_dining", "delivery"),
    (r"(?i)zomato", "food_dining", "delivery"),
    (r"(?i)ola|uber|rapido", "travel", "ride"),
    (r"(?i)paytm", "transfer", "wallet"),
    (r"(?i)gpay|googlepay", "transfer", "wallet"),
    (r"(?i)phonepe", "transfer", "wallet"),
    (r"(?i)amazon|flipkart|myntra", "shopping", "online"),
    (r"(?i)jio|airtel|bsnl|vi\b", "utility", "telecom"),
    (r"(?i)zerodha|groww|upstox", "investment", "trading"),
    (r"(?i)irctc|makemytrip", "travel", "booking"),
]

# MCC (Merchant Category Code) → category mapping
MCC_MAP: dict[str, tuple[str, str | None]] = {
    "5411": ("shopping", "grocery"),
    "5812": ("food_dining", "restaurant"),
    "5814": ("food_dining", "fast_food"),
    "4121": ("travel", "taxi"),
    "4511": ("travel", "airline"),
    "7011": ("travel", "hotel"),
    "5912": ("healthcare", "pharmacy"),
    "8011": ("healthcare", "doctor"),
    "5944": ("shopping", "jewelry"),
    "5691": ("shopping", "clothing"),
    "4900": ("utility", "electricity"),
    "4814": ("utility", "telecom"),
    "6012": ("transfer", "bank"),
    "6211": ("investment", "securities"),
}


class TransactionCategorizer:
    """AI-powered transaction categorization engine.

    Pipeline:
    1. MCC code lookup (if available) — highest confidence
    2. VPA pattern matching (for UPI transactions)
    3. Narration text pattern matching
    4. Default to 'other' with low confidence
    """

    def categorize(
        self,
        narration: str | None = None,
        merchant_name: str | None = None,
        mcc: str | None = None,
        vpa: str | None = None,
        amount_paise: int = 0,
    ) -> CategoryResult:
        """Categorize a transaction using all available signals."""

        # Step 1: MCC lookup (most reliable)
        if mcc and mcc in MCC_MAP:
            cat, subcat = MCC_MAP[mcc]
            return CategoryResult(
                primary=cat, subcategory=subcat,
                confidence=0.95, merchant_name=merchant_name,
                mcc=mcc, method="mcc",
            )

        # Step 2: VPA pattern matching
        if vpa:
            for pattern, cat, subcat in VPA_MERCHANT_PATTERNS:
                if re.search(pattern, vpa):
                    return CategoryResult(
                        primary=cat, subcategory=subcat,
                        confidence=0.88, merchant_name=self._extract_merchant_from_vpa(vpa),
                        mcc=mcc, method="vpa",
                    )

        # Step 3: Narration pattern matching
        text = " ".join(filter(None, [narration, merchant_name]))
        if text:
            for pattern, cat, subcat in NARRATION_PATTERNS:
                if re.search(pattern, text):
                    return CategoryResult(
                        primary=cat, subcategory=subcat,
                        confidence=0.78, merchant_name=merchant_name,
                        mcc=mcc, method="narration_nlp",
                    )

        # Step 4: Amount-based heuristic for P2P
        if vpa and amount_paise > 0:
            # Small UPI amounts without merchant patterns → likely P2P
            if amount_paise <= 10_000_00:  # ≤ ₹10,000
                return CategoryResult(
                    primary="upi_p2p", subcategory=None,
                    confidence=0.60, merchant_name=None,
                    mcc=mcc, method="pattern",
                )

        return CategoryResult(
            primary="other", subcategory=None,
            confidence=0.30, merchant_name=merchant_name,
            mcc=mcc, method="pattern",
        )

    @staticmethod
    def _extract_merchant_from_vpa(vpa: str) -> str | None:
        """Extract merchant name from UPI VPA (e.g., swiggy@axisbank → Swiggy)."""
        if "@" in vpa:
            handle = vpa.split("@")[0]
            # Remove numeric suffixes
            clean = re.sub(r"\d+$", "", handle)
            if clean and len(clean) > 2:
                return clean.title()
        return None
