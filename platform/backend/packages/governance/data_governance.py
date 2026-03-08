"""Data Governance — PII classification, redaction, and retention policies.

Provides:
  - PII field classification (maps table.column → sensitivity level)
  - Redaction service (mask PII in API responses based on caller role)
  - Retention policies (how long to keep data per category)
  - Field-level access control matrix
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any
import re


class SensitivityLevel(StrEnum):
    PUBLIC = "public"           # Can be shown to anyone
    INTERNAL = "internal"       # Visible to authenticated users
    CONFIDENTIAL = "confidential"  # Visible to authorized roles only
    RESTRICTED = "restricted"   # PII — must be masked in most contexts
    SECRET = "secret"           # Encryption required, minimal access


# ─── PII Field Classification ───

PII_CLASSIFICATION: dict[str, dict[str, str]] = {
    "users": {
        "email": SensitivityLevel.RESTRICTED,
        "phone": SensitivityLevel.RESTRICTED,
        "full_name": SensitivityLevel.CONFIDENTIAL,
        "password_hash": SensitivityLevel.SECRET,
    },
    "kyc_documents": {
        "document_number": SensitivityLevel.RESTRICTED,
        "extracted_data": SensitivityLevel.RESTRICTED,
        "file_path": SensitivityLevel.CONFIDENTIAL,
    },
    "kyc_extractions": {
        "full_name": SensitivityLevel.RESTRICTED,
        "date_of_birth": SensitivityLevel.RESTRICTED,
        "address": SensitivityLevel.RESTRICTED,
        "document_number": SensitivityLevel.RESTRICTED,
        "father_name": SensitivityLevel.RESTRICTED,
    },
    "beneficiaries": {
        "account_number": SensitivityLevel.RESTRICTED,
        "ifsc_code": SensitivityLevel.CONFIDENTIAL,
        "name": SensitivityLevel.CONFIDENTIAL,
        "vpa": SensitivityLevel.CONFIDENTIAL,
    },
    "payout_requests": {
        "beneficiary_name": SensitivityLevel.CONFIDENTIAL,
        "beneficiary_account": SensitivityLevel.RESTRICTED,
    },
}


# ─── Retention Policies ───

@dataclass
class RetentionPolicy:
    """How long to keep data of a given category."""
    category: str
    retention_days: int
    archive_after_days: int | None = None
    legal_hold_eligible: bool = False
    description: str = ""


RETENTION_POLICIES = [
    RetentionPolicy("transaction_data", 365 * 8, 365 * 3, True, "8 years per RBI/PMLA"),
    RetentionPolicy("kyc_documents", 365 * 8, 365 * 3, True, "8 years post account closure"),
    RetentionPolicy("audit_logs", 365 * 7, 365 * 3, True, "7 years for compliance"),
    RetentionPolicy("session_data", 90, None, False, "90 days session retention"),
    RetentionPolicy("webhook_deliveries", 365, 180, False, "1 year webhook history"),
    RetentionPolicy("ai_invocation_logs", 365 * 2, 365, False, "2 years AI audit trail"),
    RetentionPolicy("notification_records", 365, 180, False, "1 year notification history"),
    RetentionPolicy("risk_features", 365 * 3, 365, True, "3 years for model training"),
    RetentionPolicy("decision_records", 365 * 8, 365 * 3, True, "8 years for regulatory audit"),
]


# ─── Redaction Service ───

REDACTION_PATTERNS = {
    "aadhaar": (re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b"), "XXXX XXXX ****"),
    "pan": (re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b"), "XXXXX****X"),
    "phone": (re.compile(r"\b(?:\+91|0)?([6-9]\d{9})\b"), "XXXXXX****"),
    "email": (re.compile(r"\b([a-zA-Z0-9._%+-]+)@([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\b"), "****@****.***"),
    "account": (re.compile(r"\b\d{9,18}\b"), "XXXXXXXX****"),
}


class RedactionService:
    """Masks PII fields based on sensitivity level and caller role."""

    # Roles that can see restricted data
    UNRESTRICTED_ROLES = {"superadmin", "compliance_officer"}

    def redact_dict(self, data: dict, caller_role: str = "viewer") -> dict:
        """Redact PII fields in a dictionary based on caller role."""
        if caller_role in self.UNRESTRICTED_ROLES:
            return data

        redacted = {}
        for key, value in data.items():
            if isinstance(value, str):
                redacted[key] = self._redact_string(value)
            elif isinstance(value, dict):
                redacted[key] = self.redact_dict(value, caller_role)
            elif isinstance(value, list):
                redacted[key] = [
                    self.redact_dict(item, caller_role) if isinstance(item, dict)
                    else self._redact_string(item) if isinstance(item, str)
                    else item
                    for item in value
                ]
            else:
                redacted[key] = value
        return redacted

    @staticmethod
    def _redact_string(text: str) -> str:
        """Apply all PII redaction patterns to a string."""
        result = text
        for name, (pattern, replacement) in REDACTION_PATTERNS.items():
            result = pattern.sub(replacement, result)
        return result

    def get_field_sensitivity(self, table: str, column: str) -> str:
        """Get the sensitivity level of a specific field."""
        table_map = PII_CLASSIFICATION.get(table, {})
        return table_map.get(column, SensitivityLevel.INTERNAL)

    def get_retention_policy(self, category: str) -> RetentionPolicy | None:
        """Get retention policy for a data category."""
        for policy in RETENTION_POLICIES:
            if policy.category == category:
                return policy
        return None

    def classify_fields(self, table: str) -> dict[str, str]:
        """Get all classified fields for a table."""
        return PII_CLASSIFICATION.get(table, {})
