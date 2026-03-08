"""Database initialization — creates all tables from SQLAlchemy models.

Usage:
    python -m packages.db.init_db

This script:
  1. Imports all schema modules so SQLAlchemy knows about all tables
  2. Creates all tables using Base.metadata.create_all()
  3. Verifies table creation by listing all tables
  4. Works with any PostgreSQL (Aiven, Supabase, Neon, local)

For production: use Alembic migrations instead (alembic upgrade head).
This script is for initial setup / development.
"""

from __future__ import annotations

import asyncio
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from packages.core.settings import get_settings
from packages.db.base import Base

# Import ALL schema modules so Base.metadata knows about every table.
# Without these imports, create_all() would create zero tables.
import packages.schemas.auth     # noqa: F401
import packages.schemas.tenants  # noqa: F401
import packages.schemas.ledger   # noqa: F401
import packages.schemas.payouts  # noqa: F401
import packages.schemas.collections  # noqa: F401
import packages.schemas.kyc      # noqa: F401
import packages.schemas.risk     # noqa: F401
import packages.schemas.recon    # noqa: F401
import packages.schemas.webhooks # noqa: F401
import packages.schemas.audit    # noqa: F401
import packages.schemas.events   # noqa: F401


async def init_db() -> None:
    settings = get_settings()
    db_url = settings.database_url

    print(f"Connecting to: {db_url.split('@')[1] if '@' in db_url else db_url}")

    engine = create_async_engine(db_url, echo=False)

    # Create all tables
    async with engine.begin() as conn:
        # Enable pgvector extension for embedding storage
        print("Enabling pgvector extension...")
        try:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            print("pgvector enabled.")
        except Exception as e:
            print(f"pgvector not available (OK for dev): {e}")

        print("Creating tables...")
        await conn.run_sync(Base.metadata.create_all)
        print("Tables created successfully.")

    # Verify tables
    async with engine.connect() as conn:
        result = await conn.execute(text(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename"
        ))
        tables = [row[0] for row in result.fetchall()]
        print(f"\n{len(tables)} tables in database:")
        for t in tables:
            print(f"  • {t}")

    await engine.dispose()
    print("\nDatabase initialization complete.")


if __name__ == "__main__":
    try:
        asyncio.run(init_db())
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
