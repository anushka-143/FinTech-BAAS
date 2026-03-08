"""Deterministic KYB rule checks."""

from packages.kyb.service import build_kyb_checks


def test_kyb_checks_require_business_identifier() -> None:
    checks = build_kyb_checks(
        case_type="kyb",
        entity_type="pvt_ltd",
        entity_name="Acme Pvt Ltd",
        entity_id=None,
        document_types=set(),
        extracted_fields=[],
    )
    check_map = {c.check_type: c for c in checks}
    assert check_map["kyb_document_presence_gstin_or_cin"].result == "fail"
    assert check_map["kyb_incorporation_identifier_present"].result == "fail"


def test_kyb_checks_detect_name_mismatch_warn() -> None:
    checks = build_kyb_checks(
        case_type="kyb",
        entity_type="llp",
        entity_name="Acme LLP",
        entity_id="U1234",
        document_types={"gstin", "cin"},
        extracted_fields=[
            {"document_type": "gstin", "legal_name": "Acme Legal Name"},
            {"document_type": "cin", "company_name": "Different Co Name"},
        ],
    )
    check_map = {c.check_type: c for c in checks}
    assert check_map["kyb_gstin_cin_name_match"].result == "warn"


def test_kyb_checks_ignore_non_kyb_cases() -> None:
    checks = build_kyb_checks(
        case_type="kyc",
        entity_type="individual",
        entity_name="Demo User",
        entity_id=None,
        document_types={"pan"},
        extracted_fields=[{"document_type": "pan", "name": "Demo User"}],
    )
    assert checks == []
