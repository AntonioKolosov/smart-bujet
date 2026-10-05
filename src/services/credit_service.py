from __future__ import annotations

import re
import uuid
from decimal import Decimal
from typing import Sequence
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.credit import CreditAccount


class CreditService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_user_credits(
        self,
        user_id: int,
        active_only: bool = False
    ) -> Sequence[CreditAccount]:
        """Fetch all credits belonging strictly to this user (strictly isolated, non-family)."""
        conditions = [CreditAccount.user_id == user_id]
        if active_only:
            conditions.append(CreditAccount.is_active == True)

        query = (
            select(CreditAccount)
            .where(and_(*conditions))
            .order_by(CreditAccount.is_active.desc(), CreditAccount.created_at.desc())
        )
        result = await self.session.scalars(query)
        return result.all()

    async def get_credit_by_id(
        self,
        credit_id: uuid.UUID,
        user_id: int
    ) -> CreditAccount | None:
        """Fetch credit ensuring user ownership."""
        query = select(CreditAccount).where(
            CreditAccount.id == credit_id,
            CreditAccount.user_id == user_id
        )
        return await self.session.scalar(query)

    async def get_credit_summary(self, user_id: int) -> dict:
        """Aggregate total debt and active credits for user."""
        credits = await self.get_user_credits(user_id)
        active_credits = [c for c in credits if c.is_active]
        closed_credits = [c for c in credits if not c.is_active]

        total_debt = sum(c.remaining_amount for c in active_credits) if active_credits else Decimal("0.0")
        total_monthly_payment = sum(
            c.monthly_payment for c in active_credits if c.monthly_payment is not None
        ) if active_credits else Decimal("0.0")

        return {
            "total_debt": float(total_debt),
            "total_monthly_payment": float(total_monthly_payment),
            "active_credits_count": len(active_credits),
            "closed_credits_count": len(closed_credits),
            "credits_count": len(credits),
        }

    async def create_credit(
        self,
        user_id: int,
        name: str,
        original_amount: Decimal,
        currency: str = "KZT",
        bank_name: str | None = None,
        interest_rate: Decimal | None = None,
        monthly_payment: Decimal | None = None,
        remaining_amount: Decimal | None = None,
        auto_commit: bool = True
    ) -> CreditAccount:
        """Create new credit account."""
        rem_amt = remaining_amount if remaining_amount is not None else original_amount
        credit = CreditAccount(
            user_id=user_id,
            name=name.strip(),
            bank_name=bank_name.strip() if bank_name else None,
            original_amount=original_amount,
            remaining_amount=rem_amt,
            currency=currency.upper(),
            interest_rate=interest_rate,
            monthly_payment=monthly_payment,
            is_active=rem_amt > Decimal("0.0"),
            closed_at=func.now() if rem_amt <= Decimal("0.0") else None
        )
        self.session.add(credit)
        if auto_commit:
            await self.session.commit()
            await self.session.refresh(credit)
        else:
            await self.session.flush()
        return credit

    async def repay_credit(
        self,
        user_id: int,
        credit_id: uuid.UUID,
        amount: Decimal,
        auto_commit: bool = True
    ) -> tuple[CreditAccount | None, bool]:
        """
        Deduct repayment amount from remaining_amount.
        If remaining_amount reaches 0, marks as closed.
        Returns (credit, was_just_closed).
        """
        credit = await self.get_credit_by_id(credit_id, user_id)
        if not credit:
            return None, False

        curr_remaining = Decimal(str(credit.remaining_amount or 0))
        new_remaining = max(Decimal("0.0"), curr_remaining - amount)
        was_just_closed = False
        if credit.is_active and new_remaining <= Decimal("0.0"):
            credit.is_active = False
            credit.closed_at = func.now()
            was_just_closed = True

        credit.remaining_amount = new_remaining
        if auto_commit:
            await self.session.commit()
            await self.session.refresh(credit)
        else:
            await self.session.flush()
        return credit, was_just_closed

    async def delete_credit(
        self,
        credit_id: uuid.UUID,
        user_id: int
    ) -> bool:
        credit = await self.get_credit_by_id(credit_id, user_id)
        if not credit:
            return False
        await self.session.delete(credit)
        await self.session.commit()
        return True

    async def resolve_credit_account(
        self,
        user_id: int,
        target_name: str | None = None,
        credit_id_hint: str | None = None
    ) -> CreditAccount | None:
        """
        Resolve credit account using:
        1. UUID hint from AI
        2. Exact/Case-insensitive name match
        3. Token overlap match (e.g. 'каспи' in 'Каспи банк')
        4. Single active credit fallback
        """
        credits = list(await self.get_user_credits(user_id, active_only=True))
        if not credits:
            return None

        # 1. UUID hint
        if credit_id_hint:
            try:
                target_uuid = uuid.UUID(str(credit_id_hint).strip())
                for c in credits:
                    if c.id == target_uuid:
                        return c
            except (ValueError, TypeError):
                pass

        if not target_name or not target_name.strip():
            # 4. If user only has 1 active credit, match it
            if len(credits) == 1:
                return credits[0]
            return None

        norm_target = target_name.strip().lower()

        # 2. Exact match
        for c in credits:
            if c.name.strip().lower() == norm_target:
                return c
            if c.bank_name and c.bank_name.strip().lower() == norm_target:
                return c

        # 3. Substring / Token overlap match
        target_tokens = set(re.findall(r"\w+", norm_target))
        best_credit = None
        best_overlap = 0

        for c in credits:
            combined = f"{c.name} {c.bank_name or ''}".lower()
            tokens = set(re.findall(r"\w+", combined))
            overlap = len(target_tokens & tokens)
            if norm_target in combined or any(t in combined for t in target_tokens if len(t) >= 3):
                if overlap > best_overlap:
                    best_overlap = overlap
                    best_credit = c

        if best_credit:
            return best_credit

        # Fallback if single active credit
        if len(credits) == 1:
            return credits[0]

        return None
