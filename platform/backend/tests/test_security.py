"""HMAC signature tests."""

from __future__ import annotations

import time
import pytest

from packages.security.hmac_util import create_signature, verify_signature
from packages.core.errors import WebhookSignatureError


class TestHMACSignature:
    SECRET = "test-webhook-secret-key-12345"

    def test_create_and_verify(self):
        """A signature created with a secret can be verified with the same secret."""
        payload = b'{"event": "payout.success", "id": "123"}'
        sig = create_signature(payload, self.SECRET)
        assert verify_signature(payload, sig, self.SECRET)

    def test_wrong_secret_fails(self):
        """A signature verified with a different secret must fail."""
        payload = b'{"event": "payout.success"}'
        sig = create_signature(payload, self.SECRET)
        with pytest.raises(WebhookSignatureError):
            verify_signature(payload, sig, "wrong-secret")

    def test_tampered_payload_fails(self):
        """A tampered payload must fail verification."""
        payload = b'{"event": "payout.success"}'
        sig = create_signature(payload, self.SECRET)
        tampered = b'{"event": "payout.success", "amount": 999999}'
        with pytest.raises(WebhookSignatureError):
            verify_signature(tampered, sig, self.SECRET)

    def test_expired_timestamp_fails(self):
        """A signature with a timestamp older than tolerance must fail."""
        payload = b'{"data": "test"}'
        old_timestamp = int(time.time()) - 600  # 10 minutes ago
        sig = create_signature(payload, self.SECRET, timestamp=old_timestamp)
        with pytest.raises(WebhookSignatureError):
            verify_signature(payload, sig, self.SECRET, tolerance=300)

    def test_signature_format(self):
        """Signature string must follow t=<timestamp>,v1=<hex> format."""
        payload = b"test"
        sig = create_signature(payload, self.SECRET)
        assert sig.startswith("t=")
        assert ",v1=" in sig

    def test_malformed_signature_fails(self):
        """Malformed signature strings must fail."""
        payload = b"test"
        with pytest.raises(WebhookSignatureError):
            verify_signature(payload, "garbage-string", self.SECRET)


class TestRBACBasics:
    """Basic RBAC permission checks."""

    def test_viewer_has_read_permissions(self):
        from packages.security.rbac import Role, Permission, get_permissions_for_roles
        perms = get_permissions_for_roles(frozenset({Role.VIEWER}))
        assert Permission.PAYOUT_READ in perms
        assert Permission.LEDGER_READ in perms

    def test_viewer_cannot_create_payouts(self):
        from packages.security.rbac import Role, Permission, get_permissions_for_roles
        perms = get_permissions_for_roles(frozenset({Role.VIEWER}))
        assert Permission.PAYOUT_CREATE not in perms

    def test_finance_operator_can_create_payouts(self):
        from packages.security.rbac import Role, Permission, get_permissions_for_roles
        perms = get_permissions_for_roles(frozenset({Role.FINANCE_OPERATOR}))
        assert Permission.PAYOUT_CREATE in perms
        assert Permission.PAYOUT_APPROVE in perms

    def test_platform_admin_has_all_permissions(self):
        from packages.security.rbac import Role, Permission, get_permissions_for_roles
        perms = get_permissions_for_roles(frozenset({Role.PLATFORM_ADMIN}))
        for p in Permission:
            assert p in perms
