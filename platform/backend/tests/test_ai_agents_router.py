"""Tests for AI agent router grounding helpers."""

from __future__ import annotations

import enum

# Python 3.10 compatibility for environments where StrEnum is unavailable.
if not hasattr(enum, "StrEnum"):
    class _CompatStrEnum(str, enum.Enum):
        pass
    enum.StrEnum = _CompatStrEnum  # type: ignore[attr-defined]

from apps.ai_agents.router import _build_contradiction_matrix


def test_contradiction_matrix_empty_when_no_fields() -> None:
    assert _build_contradiction_matrix([]) == []


def test_contradiction_matrix_detects_pan_vs_gstin_mismatch() -> None:
    out = _build_contradiction_matrix(
        [
            {"document_type": "pan", "name": "Alice Example"},
            {"document_type": "gstin", "legal_name": "Acme Pvt Ltd"},
        ]
    )
    assert any(item["type"] == "pan_vs_gstin_name_mismatch" for item in out)


def test_contradiction_matrix_detects_gstin_vs_cin_mismatch() -> None:
    out = _build_contradiction_matrix(
        [
            {"document_type": "gstin", "legal_name": "Acme Pvt Ltd"},
            {"document_type": "cin", "company_name": "Another Legal Name"},
        ]
    )
    assert any(item["type"] == "gstin_vs_cin_name_mismatch" for item in out)
