"""Deterministic KYB checks used alongside AI recommendations.

These checks are intentionally rules-based and explainable. They do not call LLMs.
"""

from __future__ import annotations

from dataclasses import dataclass


INCORPORATED_ENTITY_TYPES = {"pvt_ltd", "llp", "public_ltd"}
BUSINESS_LIKE_ENTITY_TYPES = {
    "sole_proprietorship",
    "partnership",
    "pvt_ltd",
    "llp",
    "public_ltd",
    "trust",
    "society",
}


@dataclass(frozen=True)
class DeterministicCheck:
    check_type: str
    result: str  # pass | fail | warn
    reason: str
    details: dict



def _normalize(value: str | None) -> str:
    if not value:
        return ""
    return "".join(ch for ch in value.lower() if ch.isalnum())


def build_kyb_checks(
    *,
    case_type: str,
    entity_type: str,
    entity_name: str,
    entity_id: str | None,
    document_types: set[str],
    extracted_fields: list[dict],
) -> list[DeterministicCheck]:
    """Create deterministic KYB checks from case/doc/extraction state."""
    checks: list[DeterministicCheck] = []

    if case_type != "kyb":
        return checks

    has_gstin = "gstin" in document_types
    has_cin = "cin" in document_types

    if entity_type in BUSINESS_LIKE_ENTITY_TYPES:
        checks.append(
            DeterministicCheck(
                check_type="kyb_document_presence_gstin_or_cin",
                result="pass" if (has_gstin or has_cin or bool(entity_id)) else "fail",
                reason="Business KYB should include GSTIN/CIN evidence or entity identifier.",
                details={"has_gstin": has_gstin, "has_cin": has_cin, "entity_id_present": bool(entity_id)},
            )
        )

    if entity_type in INCORPORATED_ENTITY_TYPES:
        checks.append(
            DeterministicCheck(
                check_type="kyb_incorporation_identifier_present",
                result="pass" if (has_cin or bool(entity_id)) else "fail",
                reason="Incorporated entities must provide CIN document or incorporation identifier.",
                details={"has_cin": has_cin, "entity_id_present": bool(entity_id)},
            )
        )

    gstin_legal_name = None
    cin_company_name = None
    for item in extracted_fields:
        if not isinstance(item, dict):
            continue
        if isinstance(item.get("legal_name"), str) and item.get("document_type") == "gstin":
            gstin_legal_name = item["legal_name"]
        if isinstance(item.get("company_name"), str) and item.get("document_type") == "cin":
            cin_company_name = item["company_name"]

    if gstin_legal_name and cin_company_name:
        matched = _normalize(gstin_legal_name) == _normalize(cin_company_name)
        checks.append(
            DeterministicCheck(
                check_type="kyb_gstin_cin_name_match",
                result="pass" if matched else "warn",
                reason="GSTIN and CIN extracted entity names should align.",
                details={
                    "gstin_legal_name": gstin_legal_name,
                    "cin_company_name": cin_company_name,
                    "matched": matched,
                },
            )
        )

    sanctions_hit = any(bool(item.get("sanctions_hit")) for item in extracted_fields if isinstance(item, dict))
    checks.append(
        DeterministicCheck(
            check_type="kyb_watchlist_indicator",
            result="fail" if sanctions_hit else "pass",
            reason="Any watchlist/sanctions hit requires rejection or escalation.",
            details={"sanctions_hit": sanctions_hit, "entity_name": entity_name},
        )
    )

    return checks
