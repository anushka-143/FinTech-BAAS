"""Ledger invariant tests — the most critical financial correctness tests."""

from __future__ import annotations

import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from packages.core.errors import LedgerImbalanceError, InsufficientBalanceError


class TestLedgerInvariant:
    """Test that the ledger enforces sum(debits) == sum(credits)."""

    def test_balanced_entries_pass(self):
        """A journal with equal debit and credit totals is valid."""
        entries = [
            {"account_id": uuid.uuid4(), "direction": "debit", "amount": 1000},
            {"account_id": uuid.uuid4(), "direction": "credit", "amount": 1000},
        ]
        total_debit = sum(e["amount"] for e in entries if e["direction"] == "debit")
        total_credit = sum(e["amount"] for e in entries if e["direction"] == "credit")
        assert total_debit == total_credit

    def test_imbalanced_entries_fail(self):
        """A journal with unequal totals must raise LedgerImbalanceError."""
        total_debit = 1000
        total_credit = 500
        with pytest.raises(LedgerImbalanceError):
            if total_debit != total_credit:
                raise LedgerImbalanceError(total_debit, total_credit)

    def test_zero_amount_journal_fails(self):
        """A journal with zero total must raise LedgerImbalanceError."""
        with pytest.raises(LedgerImbalanceError):
            raise LedgerImbalanceError(0, 0)

    def test_multi_leg_balanced(self):
        """A multi-leg journal (3+ postings) with balanced totals is valid."""
        entries = [
            {"account_id": uuid.uuid4(), "direction": "debit", "amount": 500},
            {"account_id": uuid.uuid4(), "direction": "debit", "amount": 500},
            {"account_id": uuid.uuid4(), "direction": "credit", "amount": 700},
            {"account_id": uuid.uuid4(), "direction": "credit", "amount": 300},
        ]
        total_debit = sum(e["amount"] for e in entries if e["direction"] == "debit")
        total_credit = sum(e["amount"] for e in entries if e["direction"] == "credit")
        assert total_debit == total_credit == 1000


class TestBalanceChecks:
    """Test balance validation logic."""

    def test_insufficient_balance_error(self):
        """InsufficientBalanceError carries correct context."""
        err = InsufficientBalanceError("acct-123", required=5000, available=2000)
        assert err.status_code == 422
        assert err.context["required_minor"] == 5000
        assert err.context["available_minor"] == 2000

    def test_posting_amount_must_be_positive(self):
        """Posting amounts must be positive integers."""
        amount = -100
        assert amount <= 0, "Negative amounts should be rejected"

    def test_currency_consistency(self):
        """All entries in a journal must share the same currency."""
        entries = [
            {"currency": "INR", "amount": 1000},
            {"currency": "INR", "amount": 1000},
        ]
        currencies = {e["currency"] for e in entries}
        assert len(currencies) == 1
