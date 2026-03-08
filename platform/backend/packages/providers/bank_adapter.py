"""Banking partner adapter — our own integration layer.

In sandbox: simulates all banking operations locally.
In production: routes to actual banking partner APIs via NPCI/RBI/partner banks.

We are the BaaS platform. This layer connects us to the underlying
banking infrastructure (not to another BaaS).
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from packages.core.settings import get_settings


@dataclass(frozen=True)
class BankPartnerConfig:
    """Configuration for banking partner connections."""
    partner_id: str
    api_key: str
    api_secret: str
    base_url: str
    is_sandbox: bool = True


def _get_config() -> BankPartnerConfig:
    settings = get_settings()
    return BankPartnerConfig(
        partner_id=settings.bank_partner_id,
        api_key=settings.bank_partner_api_key,
        api_secret=settings.bank_partner_api_secret,
        base_url=settings.bank_partner_base_url,
        is_sandbox=settings.environment != "production",
    )


def _auth_headers(config: BankPartnerConfig) -> dict[str, str]:
    return {
        "X-Partner-ID": config.partner_id,
        "X-API-Key": config.api_key,
        "X-API-Secret": config.api_secret,
        "Content-Type": "application/json",
    }


async def bank_post(path: str, payload: dict, config: BankPartnerConfig | None = None) -> dict:
    """POST to banking partner (simulated in sandbox)."""
    cfg = config or _get_config()
    if cfg.is_sandbox:
        return _simulate_post(path, payload)

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{cfg.base_url}{path}",
            json=payload,
            headers=_auth_headers(cfg),
        )
        resp.raise_for_status()
        return resp.json()


async def bank_get(path: str, params: dict | None = None, config: BankPartnerConfig | None = None) -> dict:
    """GET from banking partner (simulated in sandbox)."""
    cfg = config or _get_config()
    if cfg.is_sandbox:
        return _simulate_get(path, params)

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            f"{cfg.base_url}{path}",
            params=params,
            headers=_auth_headers(cfg),
        )
        resp.raise_for_status()
        return resp.json()


def _simulate_post(path: str, payload: dict) -> dict:
    """Sandbox simulation — returns realistic responses without hitting real banks."""
    import uuid
    return {
        "status": "SUCCESS",
        "message": "Sandbox simulation",
        "reference_id": f"SB-{uuid.uuid4().hex[:12].upper()}",
        "data": payload,
    }


def _simulate_get(path: str, params: dict | None) -> dict:
    return {
        "status": "SUCCESS",
        "message": "Sandbox simulation",
        "data": {},
    }
