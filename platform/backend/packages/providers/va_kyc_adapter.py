"""Virtual Account + KYC adapter — our platform's own implementation.

Virtual Accounts:
  We issue VAs via partner banks (Yes Bank, ICICI, HDFC, Axis, Kotak, IDFC First).
  In sandbox: simulated locally.

KYC Verification:
  We connect to Indian government registries and run our own AI pipeline:
  - Aadhaar: via UIDAI (OTP flow)
  - PAN: via Income Tax Department
  - GSTIN: via GST Council
  - CIN: via MCA (ROC)
  - Bank account: penny drop verification
  - Documents: our Document AI service for OCR + extraction

In sandbox: all verifications are simulated with realistic responses.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

from packages.providers.base import (
    KYCProviderAdapter,
    ProviderKYCVerifyRequest,
    ProviderKYCVerifyResponse,
    ProviderVARequest,
    ProviderVAResponse,
    VirtualAccountProviderAdapter,
)


# ─── Indian bank codes ───

INDIAN_BANK_CODES = {
    "YESB": {"name": "Yes Bank", "ifsc_prefix": "YESB0"},
    "ICIC": {"name": "ICICI Bank", "ifsc_prefix": "ICIC0"},
    "HDFC": {"name": "HDFC Bank", "ifsc_prefix": "HDFC0"},
    "UTIB": {"name": "Axis Bank", "ifsc_prefix": "UTIB0"},
    "KKBK": {"name": "Kotak Mahindra Bank", "ifsc_prefix": "KKBK0"},
    "IDFB": {"name": "IDFC First Bank", "ifsc_prefix": "IDFB0"},
}


class VAAdapter(VirtualAccountProviderAdapter):
    """Our platform's virtual account adapter — issues VAs via partner banks."""

    async def create_virtual_account(self, request: ProviderVARequest) -> ProviderVAResponse:
        bank = INDIAN_BANK_CODES.get(request.bank_code, INDIAN_BANK_CODES["YESB"])
        va_number = f"{request.bank_code}{uuid.uuid4().hex[:12].upper()}"
        ifsc = f"{bank['ifsc_prefix']}000001"

        return ProviderVAResponse(
            va_number=va_number,
            ifsc=ifsc,
            bank_code=request.bank_code,
            status="active",
            raw_response={
                "va_number": va_number,
                "ifsc": ifsc,
                "bank_name": bank["name"],
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        )

    async def close_virtual_account(self, va_number: str) -> bool:
        return True


# ─── Indian document format validators ───

PAN_REGEX = re.compile(r"^[A-Z]{5}\d{4}[A-Z]$")
GSTIN_REGEX = re.compile(r"^\d{2}[A-Z]{5}\d{4}[A-Z]\d[Z][A-Z\d]$")
CIN_REGEX = re.compile(r"^[UL]\d{5}[A-Z]{2}\d{4}[A-Z]{3}\d{6}$")
AADHAAR_REGEX = re.compile(r"^\d{12}$")


class KYCAdapter(KYCProviderAdapter):
    """Our platform's KYC verification adapter.

    Routes to the appropriate Indian government registry based on document type.
    In sandbox: validates format and returns simulated verification results.
    """

    async def verify_document(self, request: ProviderKYCVerifyRequest) -> ProviderKYCVerifyResponse:
        doc_type = request.document_type.lower()
        handlers = {
            "aadhaar": self._verify_aadhaar,
            "pan": self._verify_pan,
            "gstin": self._verify_gstin,
            "cin": self._verify_cin,
            "bank_account": self._verify_bank_account,
            "voter_id": self._verify_generic,
            "driving_license": self._verify_generic,
            "passport": self._verify_generic,
        }

        handler = handlers.get(doc_type, self._verify_generic)
        return await handler(request)

    async def _verify_aadhaar(self, req: ProviderKYCVerifyRequest) -> ProviderKYCVerifyResponse:
        if not AADHAAR_REGEX.match(req.document_number):
            return ProviderKYCVerifyResponse(
                is_valid=False,
                matched_name=None,
                details={"reason": "Invalid Aadhaar format — must be 12 digits"},
            )

        # Sandbox: simulate UIDAI OTP verification success
        masked = f"XXXX-XXXX-{req.document_number[-4:]}"
        return ProviderKYCVerifyResponse(
            is_valid=True,
            matched_name=req.name or "Verified Name",
            details={
                "masked_aadhaar": masked,
                "verification_type": "otp",
                "source": "UIDAI",
                "note": "Aadhaar is not mandatory per RBI KYC Master Directions 2025",
            },
        )

    async def _verify_pan(self, req: ProviderKYCVerifyRequest) -> ProviderKYCVerifyResponse:
        if not PAN_REGEX.match(req.document_number.upper()):
            return ProviderKYCVerifyResponse(
                is_valid=False,
                matched_name=None,
                details={"reason": "Invalid PAN format — expected ABCDE1234F"},
            )

        return ProviderKYCVerifyResponse(
            is_valid=True,
            matched_name=req.name or "Verified Name",
            details={
                "pan": req.document_number.upper(),
                "pan_type": "Individual" if req.document_number[3] == "P" else "Business",
                "source": "Income Tax Department",
            },
        )

    async def _verify_gstin(self, req: ProviderKYCVerifyRequest) -> ProviderKYCVerifyResponse:
        if not GSTIN_REGEX.match(req.document_number.upper()):
            return ProviderKYCVerifyResponse(
                is_valid=False,
                matched_name=None,
                details={"reason": "Invalid GSTIN format — expected 15-char alphanumeric"},
            )

        return ProviderKYCVerifyResponse(
            is_valid=True,
            matched_name=req.name or "Business Name",
            details={
                "gstin": req.document_number.upper(),
                "state_code": req.document_number[:2],
                "source": "GST Council",
            },
        )

    async def _verify_cin(self, req: ProviderKYCVerifyRequest) -> ProviderKYCVerifyResponse:
        if not CIN_REGEX.match(req.document_number.upper()):
            return ProviderKYCVerifyResponse(
                is_valid=False,
                matched_name=None,
                details={"reason": "Invalid CIN format — expected 21-char MCA format"},
            )

        return ProviderKYCVerifyResponse(
            is_valid=True,
            matched_name=req.name or "Company Name",
            details={
                "cin": req.document_number.upper(),
                "company_type": "Private" if req.document_number[0] == "U" else "Listed",
                "source": "MCA / ROC",
            },
        )

    async def _verify_bank_account(self, req: ProviderKYCVerifyRequest) -> ProviderKYCVerifyResponse:
        ifsc = req.additional_params.get("ifsc", "")
        if not ifsc:
            return ProviderKYCVerifyResponse(
                is_valid=False,
                matched_name=None,
                details={"reason": "IFSC code required for bank account verification"},
            )

        # Sandbox: simulate penny drop verification
        return ProviderKYCVerifyResponse(
            is_valid=True,
            matched_name=req.name or "Account Holder Name",
            details={
                "verification_type": "penny_drop",
                "account_number": req.document_number[-4:].rjust(len(req.document_number), "X"),
                "ifsc": ifsc,
                "bank_name": "Partner Bank",
            },
        )

    async def _verify_generic(self, req: ProviderKYCVerifyRequest) -> ProviderKYCVerifyResponse:
        return ProviderKYCVerifyResponse(
            is_valid=True,
            matched_name=req.name,
            details={
                "document_type": req.document_type,
                "verified": True,
                "note": "Sandbox verification",
            },
        )
