"""Domain event schema tests."""

from __future__ import annotations

from packages.events.schemas import (
    PayoutRequested,
    CollectionReceived,
    LedgerJournalPosted,
    KYCCaseCreated,
    RiskAlertCreated,
    ReconBreakDetected,
)


class TestDomainEvents:
    def test_payout_event_has_correct_topic(self):
        event = PayoutRequested(
            tenant_id="t1", payout_id="p1", beneficiary_id="b1",
            amount_minor=1000, currency="INR", rail="imps",
        )
        assert event.event_type == "payout.requested"
        assert event.topic == "fintech.payout"

    def test_collection_event_topic(self):
        event = CollectionReceived(
            tenant_id="t1", virtual_account_id="va1",
            transaction_id="tx1", amount_minor=5000,
        )
        assert event.topic == "fintech.collection"

    def test_ledger_event_topic(self):
        event = LedgerJournalPosted(
            tenant_id="t1", journal_id="j1",
            reference_type="payout", reference_id="p1", total_amount=1000,
        )
        assert event.topic == "fintech.ledger"

    def test_events_are_immutable(self):
        event = KYCCaseCreated(tenant_id="t1", case_id="c1", case_type="kyc", entity_name="Test")
        try:
            event.case_id = "modified"
            assert False, "Should not be able to modify frozen dataclass"
        except AttributeError:
            pass  # Expected — events are frozen

    def test_event_id_is_auto_generated(self):
        e1 = RiskAlertCreated(tenant_id="t1", alert_id="a1", alert_type="high_risk", severity="high", entity_type="payout", entity_id="p1")
        e2 = RiskAlertCreated(tenant_id="t1", alert_id="a2", alert_type="high_risk", severity="high", entity_type="payout", entity_id="p2")
        assert e1.event_id != e2.event_id
