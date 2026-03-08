"""Alembic env.py — async migration runner."""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from packages.core.settings import get_settings
from packages.db.base import Base

# Import all schema modules so that Base.metadata picks up all tables
import packages.schemas.tenants  # noqa
import packages.schemas.auth  # noqa
import packages.schemas.ledger  # noqa
import packages.schemas.payouts  # noqa
import packages.schemas.collections  # noqa
import packages.schemas.kyc  # noqa
import packages.schemas.risk  # noqa
import packages.schemas.recon  # noqa
import packages.schemas.webhooks  # noqa
import packages.schemas.audit  # noqa
import packages.schemas.events  # noqa

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = get_settings().database_url
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = create_async_engine(get_settings().database_url)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
