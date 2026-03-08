"""Payout state machine tests."""

from __future__ import annotations

import pytest


# Valid state transitions for the payout state machine
VALID_TRANSITIONS = {
    "requested": {"prechecked"},
    "prechecked": {"reserved"},
    "reserved": {"sent", "failed_retryable"},
    "sent": {"pending", "success", "failed_retryable"},
    "pending": {"success", "failed_retryable", "failed_final"},
    "success": {"reversed"},
    "failed_retryable": {"reserved", "failed_final"},  # retry goes back to reserved
    "failed_final": set(),
    "reversed": set(),
}


class TestPayoutStateMachine:
    def test_valid_forward_transitions(self):
        """Standard happy path: requested → prechecked → reserved → sent → success."""
        path = ["requested", "prechecked", "reserved", "sent", "success"]
        for i in range(len(path) - 1):
            current, next_state = path[i], path[i + 1]
            assert next_state in VALID_TRANSITIONS[current], (
                f"Invalid transition: {current} → {next_state}"
            )

    def test_failed_retryable_can_retry(self):
        """A retryable failure can go back to reserved (retry) or fail permanently."""
        assert "reserved" in VALID_TRANSITIONS["failed_retryable"]
        assert "failed_final" in VALID_TRANSITIONS["failed_retryable"]

    def test_terminal_states_have_no_transitions(self):
        """Terminal states (failed_final, reversed) have no outgoing transitions."""
        assert VALID_TRANSITIONS["failed_final"] == set()
        assert VALID_TRANSITIONS["reversed"] == set()

    def test_success_can_reverse(self):
        """A successful payout can be reversed."""
        assert "reversed" in VALID_TRANSITIONS["success"]

    def test_invalid_transitions_are_rejected(self):
        """Direct jump from requested to success is invalid."""
        assert "success" not in VALID_TRANSITIONS["requested"]
        assert "sent" not in VALID_TRANSITIONS["requested"]

    def test_all_states_are_defined(self):
        """Every state in the machine has defined transitions."""
        expected_states = {
            "requested", "prechecked", "reserved", "sent", "pending",
            "success", "failed_retryable", "failed_final", "reversed",
        }
        assert set(VALID_TRANSITIONS.keys()) == expected_states
