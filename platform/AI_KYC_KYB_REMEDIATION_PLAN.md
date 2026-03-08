# AI-First KYC/KYB Remediation Plan

This project currently has strong scaffolding, but several flows are still partial. This plan defines what must be completed to make KYC/KYB production-grade and AI-assisted (without letting AI bypass controls).

## Current Gaps

1. **KYC/KYB AI review used shallow placeholder context** in API entrypoints.
2. **Validation check persistence mismatch** (`provider/is_passed/raw_response` vs schema fields) risked runtime errors.
3. **No explicit KYB workflow decomposition** (UBO/Director screening, GSTIN-CIN cross-check, MCA status checks) in a dedicated service layer.
4. **Frontend workflow coupling is weak**: users can submit cases, but review screens are not fully wired to AI-grounded evidence + checker actions.

## What was fixed now

- AI KYC review endpoint now loads live case/doc/extraction context from DB before invoking orchestrator.
- KYC validation check persistence now uses schema-aligned fields (`check_provider`, `result`, `details`).

## Next implementation milestones

### 1) Backend domain completion
- Add `packages/kyb/service.py` for deterministic KYB checks:
  - UBO document completeness
  - GSTIN/CIN consistency
  - sanction/watchlist hits by entity + directors
- Emit structured check records into `kyc_validation_checks` with deterministic reasons.

### 2) AI grounding and explainability
- Extend orchestrator KYC/KYB prompt context with:
  - deterministic check outcomes
  - extraction confidence distribution by document
  - contradiction matrix (PAN/GSTIN name mismatch, DOB mismatch, etc.)
- Persist AI grounding refs into case timeline for checker audit.

### 3) Maker-checker UX hardening
- Frontend KYC detail page should show 3 distinct panels:
  - deterministic checks
  - AI recommendations
  - required human verification checklist
- Block final approve action unless checker explicitly confirms checklist.

### 4) Test coverage to close confidence gap
- API tests for `/v1/ai/review/kyc/{case_id}` with realistic seeded data.
- Regression test for `KYCValidationCheck` write path (field contract).
- End-to-end smoke (seed -> create KYB -> upload docs -> AI review -> checker decision).

## Guardrails

- AI must remain advisory only.
- Only deterministic or human-approved actions can change compliance status.
- Every AI recommendation must include evidence and source grounding.
