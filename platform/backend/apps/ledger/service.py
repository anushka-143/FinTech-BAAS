"""Ledger service — double-entry accounting engine.

Core invariants:
1. Every journal must satisfy: sum(debits) == sum(credits)
2. Balances are materialized and updated transactionally with postings
3. Journal rows are immutable — corrections use compensating entries
4. Balance updates use optimistic locking via version column
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.errors import (
    ConflictError,
    InsufficientBalanceError,
    LedgerImbalanceError,
    NotFoundError,
)
from packages.events.outbox import write_outbox_event
from packages.events.schemas import LedgerJournalPosted
from packages.schemas.ledger import (
    LedgerAccount,
    LedgerBalance,
    LedgerHold,
    LedgerJournal,
    LedgerPosting,
)


class LedgerService:
    """Core ledger operations — balance-aware, ACID-compliant."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ─── Account Management ───

    async def create_account(
        self,
        *,
        tenant_id: uuid.UUID,
        code: str,
        name: str,
        account_type: str,
        currency: str = "INR",
        parent_account_id: uuid.UUID | None = None,
    ) -> LedgerAccount:
        account = LedgerAccount(
            tenant_id=tenant_id,
            code=code,
            name=name,
            account_type=account_type,
            currency=currency,
            parent_account_id=parent_account_id,
        )
        self._session.add(account)
        await self._session.flush()

        # Create the balance row
        balance = LedgerBalance(
            tenant_id=tenant_id,
            account_id=account.id,
            currency=currency,
        )
        self._session.add(balance)
        await self._session.flush()

        return account

    async def get_balance(
        self, account_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> LedgerBalance:
        stmt = select(LedgerBalance).where(
            LedgerBalance.account_id == account_id,
            LedgerBalance.tenant_id == tenant_id,
        )
        result = await self._session.execute(stmt)
        balance = result.scalar_one_or_none()
        if not balance:
            raise NotFoundError("LedgerBalance", str(account_id))
        return balance

    # ─── Journal Creation (the heart of double-entry) ───

    async def create_journal(
        self,
        *,
        tenant_id: uuid.UUID,
        reference_type: str,
        reference_id: str,
        description: str,
        entries: list[dict],  # [{"account_id": uuid, "direction": "debit"|"credit", "amount": int}]
        currency: str = "INR",
        metadata: dict | None = None,
    ) -> LedgerJournal:
        """Create a balanced journal entry with postings and update balances.

        Each entry dict must have: account_id, direction, amount (positive int in minor units).
        """
        # INVARIANT: sum(debits) == sum(credits)
        total_debit = sum(e["amount"] for e in entries if e["direction"] == "debit")
        total_credit = sum(e["amount"] for e in entries if e["direction"] == "credit")

        if total_debit != total_credit:
            raise LedgerImbalanceError(total_debit, total_credit)

        if total_debit == 0:
            raise LedgerImbalanceError(0, 0)

        journal = LedgerJournal(
            tenant_id=tenant_id,
            reference_type=reference_type,
            reference_id=reference_id,
            description=description,
            currency=currency,
            total_amount=total_debit,
            metadata_=metadata or {},
        )
        self._session.add(journal)
        await self._session.flush()

        # Create postings and update balances
        for entry in entries:
            posting = LedgerPosting(
                journal_id=journal.id,
                account_id=entry["account_id"],
                tenant_id=tenant_id,
                direction=entry["direction"],
                amount=entry["amount"],
                currency=currency,
            )
            self._session.add(posting)

            # Update materialized balance
            await self._update_balance(
                account_id=entry["account_id"],
                tenant_id=tenant_id,
                direction=entry["direction"],
                amount=entry["amount"],
            )

        # Emit domain event
        await write_outbox_event(
            self._session,
            LedgerJournalPosted(
                tenant_id=str(tenant_id),
                journal_id=str(journal.id),
                reference_type=reference_type,
                reference_id=reference_id,
                total_amount=total_debit,
                currency=currency,
            ),
        )

        return journal

    async def _update_balance(
        self,
        *,
        account_id: uuid.UUID,
        tenant_id: uuid.UUID,
        direction: str,
        amount: int,
    ) -> None:
        """Update materialized balance with optimistic locking."""
        balance = await self.get_balance(account_id, tenant_id)

        if direction == "debit":
            # For asset/expense accounts, debit increases available
            # For liability/equity/revenue accounts, debit decreases available
            # Simplified: treat all as debit=increase for now (asset-normal)
            new_available = balance.available_balance + amount
        else:
            new_available = balance.available_balance - amount

        stmt = (
            update(LedgerBalance)
            .where(
                LedgerBalance.id == balance.id,
                LedgerBalance.version == balance.version,  # optimistic lock
            )
            .values(
                available_balance=new_available,
                version=balance.version + 1,
                updated_at=datetime.now(timezone.utc),
            )
        )
        result = await self._session.execute(stmt)
        if result.rowcount == 0:
            raise ConflictError("Balance was modified concurrently, retry the operation")

    # ─── Fund Holds ───

    async def create_hold(
        self,
        *,
        tenant_id: uuid.UUID,
        account_id: uuid.UUID,
        amount: int,
        reference_type: str,
        reference_id: str,
        currency: str = "INR",
    ) -> LedgerHold:
        """Reserve funds — decreases available_balance, increases reserved_balance."""
        balance = await self.get_balance(account_id, tenant_id)

        if balance.available_balance < amount:
            raise InsufficientBalanceError(
                str(account_id), amount, balance.available_balance
            )

        hold = LedgerHold(
            tenant_id=tenant_id,
            account_id=account_id,
            amount=amount,
            currency=currency,
            reference_type=reference_type,
            reference_id=reference_id,
        )
        self._session.add(hold)

        stmt = (
            update(LedgerBalance)
            .where(
                LedgerBalance.id == balance.id,
                LedgerBalance.version == balance.version,
            )
            .values(
                available_balance=balance.available_balance - amount,
                reserved_balance=balance.reserved_balance + amount,
                version=balance.version + 1,
                updated_at=datetime.now(timezone.utc),
            )
        )
        result = await self._session.execute(stmt)
        if result.rowcount == 0:
            raise ConflictError("Balance was modified concurrently, retry the operation")

        await self._session.flush()
        return hold

    async def release_hold(
        self,
        hold_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> LedgerHold:
        """Release a held amount — returns reserved funds to available_balance."""
        stmt = select(LedgerHold).where(
            LedgerHold.id == hold_id,
            LedgerHold.tenant_id == tenant_id,
            LedgerHold.status == "active",
        )
        result = await self._session.execute(stmt)
        hold = result.scalar_one_or_none()
        if not hold:
            raise NotFoundError("LedgerHold", str(hold_id))

        hold.status = "released"
        hold.released_at = datetime.now(timezone.utc)

        balance = await self.get_balance(hold.account_id, tenant_id)
        stmt = (
            update(LedgerBalance)
            .where(
                LedgerBalance.id == balance.id,
                LedgerBalance.version == balance.version,
            )
            .values(
                available_balance=balance.available_balance + hold.amount,
                reserved_balance=balance.reserved_balance - hold.amount,
                version=balance.version + 1,
                updated_at=datetime.now(timezone.utc),
            )
        )
        await self._session.execute(stmt)
        return hold

    async def capture_hold(
        self,
        hold_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> LedgerHold:
        """Capture a hold — moves funds from reserved to settled (used after payout success)."""
        stmt = select(LedgerHold).where(
            LedgerHold.id == hold_id,
            LedgerHold.tenant_id == tenant_id,
            LedgerHold.status == "active",
        )
        result = await self._session.execute(stmt)
        hold = result.scalar_one_or_none()
        if not hold:
            raise NotFoundError("LedgerHold", str(hold_id))

        hold.status = "captured"
        hold.captured_at = datetime.now(timezone.utc)

        balance = await self.get_balance(hold.account_id, tenant_id)
        stmt = (
            update(LedgerBalance)
            .where(
                LedgerBalance.id == balance.id,
                LedgerBalance.version == balance.version,
            )
            .values(
                reserved_balance=balance.reserved_balance - hold.amount,
                version=balance.version + 1,
                updated_at=datetime.now(timezone.utc),
            )
        )
        await self._session.execute(stmt)
        return hold
