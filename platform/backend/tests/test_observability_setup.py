"""Tests for logging setup helpers."""

from packages.observability.setup import _resolve_log_level


def test_resolve_named_log_level() -> None:
    assert _resolve_log_level("debug") == 10


def test_resolve_numeric_log_level() -> None:
    assert _resolve_log_level("30") == 30


def test_invalid_level_falls_back_to_info() -> None:
    assert _resolve_log_level("not-a-level") == 20
