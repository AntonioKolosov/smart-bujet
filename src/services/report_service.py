from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID
from sqlalchemy import select, func, and_, or_, case
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.transaction import Transaction
from src.models.category import Category, CategoryType
from src.models.asset import AssetAccount
from src.models.credit import CreditAccount
from src.models.user import User


CATEGORY_UI_META: dict[str, dict[str, str]] = {
    "Еда вне дома": {"color": "#f97316", "icon": "🍽️"},
    "Продукты": {"color": "#22c55e", "icon": "🛒"},
    "Транспорт": {"color": "#38bdf8", "icon": "🚕"},
    "Развлечения": {"color": "#a855f7", "icon": "🎉"},
    "Здоровье": {"color": "#ec4899", "icon": "💊"},
    "Обязательные расходы": {"color": "#eab308", "icon": "⚡"},
    "Подписки": {"color": "#6366f1", "icon": "📱"},
    "Ребёнок": {"color": "#14b8a6", "icon": "👶"},
    "Питомец": {"color": "#84cc16", "icon": "🐾"},
    "Образование": {"color": "#06b6d4", "icon": "📚"},
    "Подарок": {"color": "#f43f5e", "icon": "🎁"},
    "Ремонт": {"color": "#f59e0b", "icon": "🛠️"},
    "Шоппинг": {"color": "#d946ef", "icon": "🛍️"},
    "Прочее": {"color": "#94a3b8", "icon": "📦"},
    "Погашение кредита": {"color": "#ef4444", "icon": "💳"},
    "Денежный перевод": {"color": "#8b5cf6", "icon": "💸"},
}

FALLBACK_COLORS = ["#f97316", "#22c55e", "#38bdf8", "#a855f7", "#ec4899", "#eab308", "#6366f1", "#14b8a6", "#84cc16", "#06b6d4", "#f43f5e", "#94a3b8"]

def get_category_ui_meta(name: str, index: int = 0) -> dict[str, str]:
    if name in CATEGORY_UI_META:
        return CATEGORY_UI_META[name]
    color = FALLBACK_COLORS[index % len(FALLBACK_COLORS)]
    return {"color": color, "icon": "🏷️"}

MONTH_NAMES_RU = [
    "", "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"
]

MONTH_SHORT_RU = [
    "", "Янв", "Фев", "Мар", "Апр", "Май", "Июн",
    "Июл", "Авг", "Сен", "Окт", "Ноя", "Дек"
]


@dataclass
class AnalyticsSummaryData:
    period: str
    period_label: str
    currency: str
    total_expense: float
    total_income: float
    net_savings: float
    saving_rate: float
    top_category_name: str | None
    top_category_amount: float
    top_category_share: float
    top_categories: list[dict[str, Any]]
    current_liquid_balance: float
    total_deposit_balance: float
    total_credit_debt: float
    monthly_credit_payment: float
    debt_burden_ratio: float
    runway_months: float
    is_family: bool
    family_members_count: int = 1


class ReportService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_summary(
        self,
        user_id: int,
        family_group_id: UUID | None = None,
        period: str = "month"  # "week", "month", "year"
    ) -> dict[str, Any]:
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
            conditions.append(Transaction.related_transaction_id.is_(None))
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

    async def get_category_breakdown(
        self,
        user_id: int,
        family_group_id: UUID | None = None,
        period: str = "month"
    ) -> dict[str, Any]:
        """Category spending breakdown for current calendar month."""
        now = datetime.now(timezone.utc)
        start_date = datetime(now.year, now.month, 1, 0, 0, 0, tzinfo=timezone.utc)
        if now.month == 12:
            end_date = datetime(now.year + 1, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        else:
            end_date = datetime(now.year, now.month + 1, 1, 0, 0, 0, tzinfo=timezone.utc)

        conditions = [
            Transaction.transaction_date >= start_date,
            Transaction.transaction_date < end_date,
            Transaction.type == CategoryType.expense
        ]

        if family_group_id:
            conditions.append(Transaction.family_group_id == family_group_id)
            conditions.append(Transaction.related_transaction_id.is_(None))
        else:
            conditions.append(Transaction.user_id == user_id)

        query = (
            select(
                Category.name,
                func.coalesce(func.sum(Transaction.amount), 0).label("total"),
                func.count(Transaction.id).label("cnt")
            )
            .join(Category, Transaction.category_id == Category.id)
            .where(and_(*conditions))
            .group_by(Category.name)
            .order_by(func.sum(Transaction.amount).desc())
        )
        rows = (await self.session.execute(query)).all()
        total_spend = sum(float(r.total) for r in rows)

        items = []
        for idx, r in enumerate(rows):
            amt = float(r.total)
            pct = round((amt / total_spend * 100), 1) if total_spend > 0 else 0.0
            meta = get_category_ui_meta(r.name, idx)
            items.append({
                "name": r.name,
                "amount": round(amt, 2),
                "percentage": pct,
                "tx_count": int(r.cnt),
                "color": meta["color"],
                "icon": meta["icon"]
            })

        period_title = f"{MONTH_NAMES_RU[now.month]} {now.year}"
        return {
            "total_spend": round(total_spend, 2),
            "currency": "KZT",
            "period_label": period_title,
            "categories": items
        }

    async def get_monthly_dynamics(
        self,
        user_id: int,
        family_group_id: UUID | None = None,
        months_count: int = 6
    ) -> dict[str, Any]:
        """Monthly spending and income dynamics for the past N calendar months."""
        now = datetime.now(timezone.utc)
        cur_year, cur_month = now.year, now.month
        month_keys: list[tuple[int, int]] = []
        for i in range(months_count - 1, -1, -1):
            y = cur_year
            m = cur_month - i
            while m <= 0:
                m += 12
                y -= 1
            month_keys.append((y, m))

        first_y, first_m = month_keys[0]
        start_date = datetime(first_y, first_m, 1, 0, 0, 0, tzinfo=timezone.utc)

        conditions = [
            Transaction.transaction_date >= start_date,
            Transaction.type.in_([CategoryType.expense, CategoryType.income])
        ]
        if family_group_id:
            conditions.append(Transaction.family_group_id == family_group_id)
            conditions.append(Transaction.related_transaction_id.is_(None))
        else:
            conditions.append(Transaction.user_id == user_id)

        month_trunc = func.date_trunc("month", Transaction.transaction_date)
        query = (
            select(
                month_trunc.label("m_date"),
                Transaction.type,
                func.coalesce(func.sum(Transaction.amount), 0).label("total")
            )
            .where(and_(*conditions))
            .group_by("m_date", Transaction.type)
            .order_by("m_date")
        )
        rows = (await self.session.execute(query)).all()

        data_map: dict[tuple[int, int], dict[str, float]] = {}
        for r in rows:
            d = r.m_date
            key = (d.year, d.month)
            if key not in data_map:
                data_map[key] = {"expense": 0.0, "income": 0.0}
            if r.type == CategoryType.expense:
                data_map[key]["expense"] = float(r.total)
            elif r.type == CategoryType.income:
                data_map[key]["income"] = float(r.total)

        history: list[dict[str, Any]] = []
        expense_values: list[float] = []
        for (y, m) in month_keys:
            exp = data_map.get((y, m), {}).get("expense", 0.0)
            inc = data_map.get((y, m), {}).get("income", 0.0)
            history.append({
                "year": y,
                "month": m,
                "label": MONTH_SHORT_RU[m],
                "total_expense": round(exp, 2),
                "total_income": round(inc, 2),
                "net_savings": round(inc - exp, 2)
            })
            expense_values.append(exp)

        cur_spend = expense_values[-1] if expense_values else 0.0
        avg_spend = sum(expense_values) / len(expense_values) if expense_values else 0.0

        cat_data = await self.get_category_breakdown(user_id, family_group_id, "month")
        top_cat = cat_data["categories"][0] if cat_data["categories"] else None

        metrics = {
            "current_month_spend": round(cur_spend, 2),
            "monthly_average_spend": round(avg_spend, 2),
            "top_category_name": top_cat["name"] if top_cat else None,
            "top_category_amount": top_cat["amount"] if top_cat else None,
            "top_category_percent": top_cat["percentage"] if top_cat else None
        }

        return {
            "currency": "KZT",
            "months_count": months_count,
            "history": history,
            "metrics": metrics
        }

    @staticmethod
    def get_period_bounds(period: str, ref_date: datetime | None = None) -> tuple[datetime, datetime, str]:
        """Calculates start_date, end_date and human-readable label in UTC."""
        now = ref_date or datetime.now(timezone.utc)

        if period == "week":
            start_date = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = now
            label = f"Неделя ({start_date.strftime('%d.%m')} - {end_date.strftime('%d.%m')})"
        elif period == "year":
            start_date = datetime(now.year, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
            end_date = now
            label = f"{now.year} год"
        else:  # default "month"
            start_date = datetime(now.year, now.month, 1, 0, 0, 0, tzinfo=timezone.utc)
            end_date = now
            label = f"{MONTH_NAMES_RU[now.month]} {now.year}"

        return start_date, end_date, label

    async def get_agent_analytics(
        self,
        user_id: int,
        family_group_id: UUID | None = None,
        period: str = "month",
        ref_date: datetime | None = None
    ) -> AnalyticsSummaryData:
        """
        Executes single-pass SQL aggregations for:
        1. Period cashflow (income, expense, savings).
        2. Top category breakdown & share.
        3. Balance snapshot (liquid, deposits, credits, runway).
        """
        start_date, end_date, period_label = self.get_period_bounds(period, ref_date)

        user = await self.session.get(User, user_id)
        currency = user.currency if user else "KZT"
        is_family = bool(family_group_id)

        if is_family:
            members_res = await self.session.scalars(
                select(User).where(User.family_group_id == family_group_id)
            )
            members = list(members_res.all())
            target_user_ids = [m.id for m in members] or [user_id]
            family_members_count = len(target_user_ids)
            initial_balance = sum(float(m.initial_balance or 0.0) for m in members)
        else:
            target_user_ids = [user_id]
            family_members_count = 1
            initial_balance = float(user.initial_balance or 0.0) if user else 0.0

        conditions = [
            Transaction.user_id.in_(target_user_ids),
            Transaction.transaction_date >= start_date,
            Transaction.transaction_date <= end_date,
        ]
        if is_family:
            conditions.append(Transaction.related_transaction_id.is_(None))

        cashflow_query = (
            select(
                func.coalesce(func.sum(case((Transaction.type == CategoryType.expense, Transaction.amount), else_=0)), 0).label("expense"),
                func.coalesce(func.sum(case((and_(Transaction.type == CategoryType.income, Transaction.related_transaction_id.is_(None)), Transaction.amount), else_=0)), 0).label("income"),
            )
            .where(and_(*conditions))
        )
        cf_row = (await self.session.execute(cashflow_query)).one()
        total_expense = float(cf_row.expense)
        total_income = float(cf_row.income)
        net_savings = total_income - total_expense
        saving_rate = round((net_savings / total_income * 100), 1) if total_income > 0 else 0.0

        top_cats_query = (
            select(
                Category.name.label("name"),
                func.coalesce(func.sum(Transaction.amount), 0).label("total")
            )
            .join(Category, Transaction.category_id == Category.id)
            .where(and_(*conditions, Transaction.type == CategoryType.expense))
            .group_by(Category.name)
            .order_by(func.sum(Transaction.amount).desc())
            .limit(5)
        )
        cat_rows = (await self.session.execute(top_cats_query)).all()
        top_categories = []
        for r in cat_rows:
            amt = float(r.total)
            share = round((amt / total_expense * 100), 1) if total_expense > 0 else 0.0
            top_categories.append({"name": r.name, "amount": amt, "share": share})

        top_cat = top_categories[0] if top_categories else None
        top_category_name = top_cat["name"] if top_cat else None
        top_category_amount = top_cat["amount"] if top_cat else 0.0
        top_category_share = top_cat["share"] if top_cat else 0.0

        liquid_query = (
            select(
                func.coalesce(func.sum(case((and_(Transaction.type == CategoryType.income, Transaction.asset_account_id.is_(None)), Transaction.amount), else_=0)), 0).label("liquid_inc"),
                func.coalesce(func.sum(case((Transaction.type == CategoryType.expense, Transaction.amount), else_=0)), 0).label("exp"),
                func.coalesce(func.sum(case((Transaction.type == CategoryType.transfer_out, Transaction.amount), else_=0)), 0).label("tout"),
                func.coalesce(func.sum(case((Transaction.type == CategoryType.transfer_in, Transaction.amount), else_=0)), 0).label("tin"),
            )
            .where(Transaction.user_id.in_(target_user_ids))
        )
        l_row = (await self.session.execute(liquid_query)).one()
        current_liquid_balance = round(
            initial_balance + float(l_row.liquid_inc) - float(l_row.exp) - float(l_row.tout) + float(l_row.tin), 2
        )

        deposit_query = (
            select(func.coalesce(func.sum(AssetAccount.balance), 0))
            .where(AssetAccount.user_id.in_(target_user_ids), AssetAccount.is_active.is_(True))
        )
        total_deposit_balance = round(float(await self.session.scalar(deposit_query) or 0.0), 2)

        credit_query = (
            select(
                func.coalesce(func.sum(CreditAccount.remaining_amount), 0).label("debt"),
                func.coalesce(func.sum(CreditAccount.monthly_payment), 0).label("payment")
            )
            .where(CreditAccount.user_id.in_(target_user_ids), CreditAccount.is_active.is_(True))
        )
        cr_row = (await self.session.execute(credit_query)).one()
        total_credit_debt = round(float(cr_row.debt), 2)
        monthly_credit_payment = round(float(cr_row.payment), 2)

        if period == "week":
            effective_monthly_expense = total_expense * 4.33
            effective_monthly_income = total_income * 4.33
        elif period == "year":
            effective_monthly_expense = total_expense / 12.0
            effective_monthly_income = total_income / 12.0
        else:
            effective_monthly_expense = total_expense
            effective_monthly_income = total_income

        debt_burden_ratio = (
            round((monthly_credit_payment / effective_monthly_income * 100), 1)
            if effective_monthly_income > 0 else 0.0
        )
        total_cushion = max(0.0, current_liquid_balance) + total_deposit_balance
        runway_months = (
            round((total_cushion / effective_monthly_expense), 2)
            if effective_monthly_expense > 0 else 99.0
        )

        return AnalyticsSummaryData(
            period=period,
            period_label=period_label,
            currency=currency,
            total_expense=round(total_expense, 2),
            total_income=round(total_income, 2),
            net_savings=round(net_savings, 2),
            saving_rate=saving_rate,
            top_category_name=top_category_name,
            top_category_amount=round(top_category_amount, 2),
            top_category_share=top_category_share,
            top_categories=top_categories,
            current_liquid_balance=current_liquid_balance,
            total_deposit_balance=total_deposit_balance,
            total_credit_debt=total_credit_debt,
            monthly_credit_payment=monthly_credit_payment,
            debt_burden_ratio=debt_burden_ratio,
            runway_months=runway_months,
            is_family=is_family,
            family_members_count=family_members_count
        )



