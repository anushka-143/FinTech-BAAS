"""Seed script — creates demo tenant, user, and ledger accounts for local development.

Usage: python -m packages.db.seed
"""

from __future__ import annotations

import asyncio
import uuid

from passlib.hash import bcrypt
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.engine import get_session_factory
from packages.db.base import Base
from packages.db.engine import get_engine
from packages.schemas.tenants import Tenant, TenantFeature, APIKey
from packages.schemas.auth import User
from packages.schemas.ledger import LedgerAccount, LedgerBalance
from packages.security.auth import generate_api_key


DEMO_TENANT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
DEMO_USER_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")


async def seed() -> None:
    engine = get_engine()

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = get_session_factory()
    async with factory() as session:
        # ─── Tenant ───
        tenant = Tenant(
            id=DEMO_TENANT_ID,
            name="Demo Fintech Corp",
            slug="demo-fintech",
            environment="development",
        )
        session.add(tenant)

        # ─── Features ───
        for feature in ["payouts", "collections", "kyc", "risk", "ai_copilot"]:
            session.add(TenantFeature(
                tenant_id=DEMO_TENANT_ID,
                feature_key=feature,
                is_enabled=True,
            ))

        # ─── User ───
        user = User(
            id=DEMO_USER_ID,
            tenant_id=DEMO_TENANT_ID,
            email="admin@demo-fintech.com",
            password_hash=bcrypt.hash("demo1234"),
            full_name="Demo Admin",
            role="tenant_admin",
            permissions=["*"],
        )
        session.add(user)

        # ─── API Key ───
        raw_key, key_hash, key_prefix = generate_api_key()
        api_key = APIKey(
            tenant_id=DEMO_TENANT_ID,
            key_hash=key_hash,
            key_prefix=key_prefix,
            label="Demo API Key",
            scopes=["*"],
            created_by=DEMO_USER_ID,
        )
        session.add(api_key)

        # ─── Ledger accounts ───
        accounts = [
            ("WALLET", "Customer Wallet - Available", "asset"),
            ("WALLET-RESERVE", "Customer Wallet - Reserve", "asset"),
            ("PENDING-IN", "Pending Inbound", "asset"),
            ("PENDING-OUT", "Pending Outbound", "asset"),
            ("BANK-CLEARING", "Bank Clearing", "asset"),
            ("PAYOUT-RESERVE", "Payout Reserve", "liability"),
            ("PROVIDER-CLEARING", "Provider Clearing", "liability"),
            ("FEE-REVENUE", "Fee Revenue", "revenue"),
            ("PLATFORM-EQUITY", "Platform Equity", "equity"),
        ]

        for code, name, acct_type in accounts:
            acct = LedgerAccount(
                id=uuid.uuid4(),
                tenant_id=DEMO_TENANT_ID,
                code=code,
                name=name,
                account_type=acct_type,
                currency="INR",
            )
            session.add(acct)
            await session.flush()

            balance = LedgerBalance(
                tenant_id=DEMO_TENANT_ID,
                account_id=acct.id,
                currency="INR",
                available_balance=10_000_000_00 if code == "WALLET" else 0,  # 1 crore paise = 1 lakh INR
            )
            session.add(balance)

        await session.commit()

    print("✓ Seed data created successfully")
    print(f"  Tenant ID:  {DEMO_TENANT_ID}")
    print(f"  User email: admin@demo-fintech.com")
    print(f"  Password:   demo1234")
    print(f"  API Key:    {raw_key}")
    print(f"  Key Prefix: {key_prefix}")
    print()
    print("Use these headers for API calls:")
    print(f'  X-Tenant-ID: {DEMO_TENANT_ID}')
    print(f'  X-User-ID: {DEMO_USER_ID}')
    print(f'  X-User-Roles: tenant_admin')

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
