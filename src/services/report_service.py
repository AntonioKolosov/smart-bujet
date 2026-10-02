from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List
from uuid import UUID
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.transaction import Transaction
from src.models.category import Category, CategoryType


class ReportService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_summary(
        self,
        user_id: int,
        family_group_id: Optional[UUID] = None,
        period: str = "month"  # "week", "month", "year"
    ) -> Dict[str, Any]:
        """Generate financial summary and category breakdown for a given period."""
        now = datetime.now(timezone.utc)
        if period == "week":
            start_date = now - timedelta(days=7)
        elif period == "year":
            start_date = now - timedelta(days=365)
        else:
            start_date = now - timedelta(days=30)

        conditions = [Transaction.transaction_date >= start_date]
        if family_group_id:
            conditions.append(or_(
                Transaction.user_id == user_id,
                Transaction.family_group_id == family_group_id
            ))
        else:
            conditions.append(Transaction.user_id == user_id)

        # Query total income and expense
        income_query = (
            select(func.coalesce(func.sum(Transaction.amount), 0))
            .where(and_(*conditions, Transaction.type == CategoryType.income))
        )
        expense_query = (
            select(func.coalesce(func.sum(Transaction.amount), 0))
            .where(and_(*conditions, Transaction.type == CategoryType.expense))
        )

        total_income = float(await self.session.scalar(income_query) or 0)
        total_expense = float(await self.session.scalar(expense_query) or 0)
        balance = total_income - total_expense

        # Category breakdown for expenses
        cat_query = (
            select(
                Category.name,
                func.sum(Transaction.amount).label("total")
            )
            .join(Category, Transaction.category_id == Category.id)
            .where(and_(*conditions, Transaction.type == CategoryType.expense))
            .group_by(Category.name)
            .order_by(func.sum(Transaction.amount).desc())
        )
        cat_result = await self.session.execute(cat_query)
        categories = [
            {"category": row[0], "total": float(row[1])}
            for row in cat_result.all()
        ]

        return {
            "period": period,
            "start_date": start_date.isoformat(),
            "total_income": total_income,
            "total_expense": total_expense,
            "balance": balance,
            "categories": categories
        }

