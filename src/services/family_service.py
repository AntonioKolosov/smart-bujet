import secrets
import logging
from datetime import datetime, timezone
from typing import Optional, List, Tuple
from uuid import UUID
from sqlalchemy import select, or_, desc, func
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.user import User
from src.models.family import FamilyGroup
from src.models.category import CategoryType
from src.models.transaction import Transaction
from src.services.transaction_service import TransactionService
from src.core.config import settings

logger = logging.getLogger(__name__)


class FamilyService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.tx_service = TransactionService(session)

    async def get_or_create_user_family(self, user: User) -> FamilyGroup:
        """
        Auto-provisioning: Ensures the user belongs to a FamilyGroup.
        If user has no group, creates a personalized family group with unique invite code.
        """
        if user.family_group_id:
            group = await self.session.get(FamilyGroup, user.family_group_id)
            if group:
                return group

        invite_code = secrets.token_urlsafe(8)
        base_name = f"Семья {user.first_name}".strip() if user.first_name else "Семейный бюджет"
        group = FamilyGroup(
            name=base_name,
            owner_id=user.id,
            invite_code=invite_code
        )
        self.session.add(group)
        await self.session.flush()

        user.family_group_id = group.id
        await self.session.commit()
        await self.session.refresh(group)
        return group

    def build_invite_link(self, invite_code: str) -> str:
        bot_name = getattr(settings, "bot_username", "smartbujetbot")
        return f"https://t.me/{bot_name}?start=fam_{invite_code}"

    async def get_family_summary(self, user: User) -> dict:
        """
        Aggregated Family Summary:
        - Combined liquid balance = sum(member.current_balance)
        - Combined month expense = sum(member.month_expense) with intercompany elimination
        - Combined month income = sum(member.month_income) with intercompany elimination
        - If len(members) < 2 -> state: single_member (invite link visible)
        - If len(members) >= 2 -> state: active_family (invite link HIDDEN)
        """
        group = await self.get_or_create_user_family(user)

        members_query = (
            select(User)
            .where(User.family_group_id == group.id)
            .order_by(desc(User.id == group.owner_id), User.id)
        )
        members_res = await self.session.scalars(members_query)
        members: List[User] = members_res.all()

        members_info = []
        combined_balance = 0.0
        combined_month_expense = 0.0
        combined_month_income = 0.0
        month_period_name = "Текущий месяц"

        for m in members:
            bal_data = await self.tx_service.get_user_balance(m.id)
            c_bal = float(bal_data["current_balance"])
            m_exp = float(bal_data["month_expense"])
            m_inc = float(bal_data["month_income"])
            month_period_name = bal_data.get("month_period_name", month_period_name)

            combined_balance += c_bal
            combined_month_expense += m_exp
            combined_month_income += m_inc

            display_name = m.first_name or m.username or f"Участник {m.id}"
            members_info.append({
                "id": m.id,
                "first_name": display_name,
                "username": m.username,
                "currency": m.currency,
                "current_balance": c_bal,
                "month_expense": m_exp,
                "month_income": m_inc,
                "is_owner": (m.id == group.owner_id),
                "is_current_user": (m.id == user.id)
            })

        is_active = len(members) >= 2
        status_str = "active_family" if is_active else "single_member"

        # Intercompany elimination: exclude intra-family transfers from combined external family cashflow
        now = datetime.now(timezone.utc)
        start_month = datetime(now.year, now.month, 1, 0, 0, 0, tzinfo=timezone.utc)
        if now.month == 12:
            next_month = datetime(now.year + 1, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        else:
            next_month = datetime(now.year, now.month + 1, 1, 0, 0, 0, tzinfo=timezone.utc)

        intra_family_expense = await self.session.scalar(
            select(func.coalesce(func.sum(Transaction.amount), 0))
            .where(
                Transaction.family_group_id == group.id,
                Transaction.type == CategoryType.expense,
                Transaction.related_transaction_id.is_not(None),
                Transaction.transaction_date >= start_month,
                Transaction.transaction_date < next_month,
            )
        ) or 0

        intra_family_income = await self.session.scalar(
            select(func.coalesce(func.sum(Transaction.amount), 0))
            .where(
                Transaction.family_group_id == group.id,
                Transaction.type == CategoryType.income,
                Transaction.related_transaction_id.is_not(None),
                Transaction.transaction_date >= start_month,
                Transaction.transaction_date < next_month,
            )
        ) or 0

        consolidated_month_expense = max(0.0, combined_month_expense - float(intra_family_expense))
        consolidated_month_income = max(0.0, combined_month_income - float(intra_family_income))

        return {
            "group_id": group.id,
            "name": group.name,
            "status": status_str,
            "is_owner": (user.id == group.owner_id),
            "invite_code": group.invite_code if not is_active else None,
            "invite_link": self.build_invite_link(group.invite_code) if not is_active else None,
            "member_count": len(members),
            "combined_balance": round(combined_balance, 2),
            "combined_month_expense": round(consolidated_month_expense, 2),
            "combined_month_income": round(consolidated_month_income, 2),
            "currency": user.currency or "KZT",
            "month_period_name": month_period_name,
            "members": members_info
        }

    async def get_family_transactions(self, user: User, limit: int = 60, offset: int = 0) -> List[dict]:
        """
        Joint Feed:
        Fetches all transactions for family members with author badges without N+1 overhead.
        """
        group = await self.get_or_create_user_family(user)
        members_query = select(User.id).where(User.family_group_id == group.id)
        member_ids = (await self.session.scalars(members_query)).all()

        if not member_ids:
            return []

        query = (
            select(Transaction)
            .options(joinedload(Transaction.category), joinedload(Transaction.user))
            .where(
                or_(
                    Transaction.family_group_id == group.id,
                    Transaction.user_id.in_(member_ids)
                )
            )
            .order_by(desc(Transaction.transaction_date))
            .offset(offset)
            .limit(limit)
        )
        txs = (await self.session.scalars(query)).unique().all()

        result = []
        for tx in txs:
            author_name = "Вы" if tx.user_id == user.id else (tx.user.first_name or tx.user.username or "Партнёр")
            result.append({
                "id": tx.id,
                "user_id": tx.user_id,
                "author_name": author_name,
                "author_username": tx.user.username if tx.user else None,
                "is_current_user": (tx.user_id == user.id),
                "amount": float(tx.amount),
                "original_amount": float(tx.original_amount) if tx.original_amount else None,
                "discount_amount": float(tx.discount_amount) if tx.discount_amount else None,
                "type": tx.type.value if hasattr(tx.type, "value") else str(tx.type),
                "category_id": tx.category_id,
                "category_name": tx.category.name if tx.category else None,
                "item_name": tx.item_name,
                "raw_text": tx.raw_text,
                "source": tx.source.value if hasattr(tx.source, "value") else str(tx.source),
                "transaction_date": tx.transaction_date
            })
        return result

    async def join_by_invite(self, user: User, invite_code: str) -> Tuple[Optional[FamilyGroup], Optional[int], str]:
        """
        Joins an existing group by deep-link invite code.
        Returns: (group, partner_id_to_notify, message)
        """
        code = invite_code.strip()
        query = select(FamilyGroup).where(FamilyGroup.invite_code == code)
        group = await self.session.scalar(query)
        if not group:
            return None, None, "Семейная группа с таким кодом не найдена."

        if user.family_group_id == group.id:
            return group, None, "Вы уже состоите в этой семейной группе."

        # If user is in an existing single-member solo group, detach gracefully
        if user.family_group_id:
            old_group = await self.session.get(FamilyGroup, user.family_group_id)
            if old_group:
                other_members = await self.session.scalar(
                    select(User.id).where(User.family_group_id == old_group.id, User.id != user.id)
                )
                if other_members:
                    return None, None, f"Вы уже состоите в группе «{old_group.name}». Сначала покиньте её."
                # Delete empty solo group
                await self.session.delete(old_group)

        user.family_group_id = group.id
        await self.session.commit()
        await self.session.refresh(group)

        # Find partner to notify
        partner_query = select(User.id).where(User.family_group_id == group.id, User.id != user.id)
        partner_id = await self.session.scalar(partner_query)

        return group, partner_id, f"Вы успешно присоединились к группе «{group.name}»!"

    async def leave_group(self, user: User) -> Tuple[bool, Optional[int]]:
        """
        Leaves current family group. Returns (success, partner_id_to_notify).
        """
        if not user.family_group_id:
            return False, None

        group_id = user.family_group_id
        partner_query = select(User.id).where(User.family_group_id == group_id, User.id != user.id)
        partner_id = await self.session.scalar(partner_query)

        user.family_group_id = None
        await self.session.commit()

        # If group is now empty, delete it
        remaining_members = await self.session.scalar(
            select(User.id).where(User.family_group_id == group_id)
        )
        if not remaining_members:
            old_group = await self.session.get(FamilyGroup, group_id)
            if old_group:
                await self.session.delete(old_group)
                await self.session.commit()

        return True, partner_id
