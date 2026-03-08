"""HMAC signature creation and verification for webhooks."""

from __future__ import annotations

import hashlib
import hmac
import time

from packages.core.errors import WebhookSignatureError


TIMESTAMP_TOLERANCE_SECONDS = 300  # 5 minutes


def create_signature(payload: bytes, secret: str, timestamp: int | None = None) -> str:
    """Create HMAC-SHA256 signature with timestamp for replay protection."""
    ts = timestamp or int(time.time())
    message = f"{ts}.{payload.decode()}"
    sig = hmac.new(
        secret.encode(),
        message.encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"t={ts},v1={sig}"


def verify_signature(
    payload: bytes,
    signature_header: str,
    secret: str,
    tolerance: int = TIMESTAMP_TOLERANCE_SECONDS,
) -> bool:
    """Verify HMAC-SHA256 signature with timestamp tolerance.

    Signature format: t=<unix_timestamp>,v1=<hex_digest>
    """
    parts = {}
    for part in signature_header.split(","):
        key, _, value = part.partition("=")
        parts[key.strip()] = value.strip()

    timestamp_str = parts.get("t")
    received_sig = parts.get("v1")

    if not timestamp_str or not received_sig:
        raise WebhookSignatureError()

    try:
        timestamp = int(timestamp_str)
    except ValueError:
        raise WebhookSignatureError()

    # Replay protection
    current_time = int(time.time())
    if abs(current_time - timestamp) > tolerance:
        raise WebhookSignatureError()

    # Recompute
    message = f"{timestamp}.{payload.decode()}"
    expected_sig = hmac.new(
        secret.encode(),
        message.encode(),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(received_sig, expected_sig):
        raise WebhookSignatureError()

    return True
