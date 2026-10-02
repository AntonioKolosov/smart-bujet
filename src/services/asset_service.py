from decimal import Decimal
from typing import List, Optional, Dict, Any
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.user import User
from src.models.asset import AssetAccount, AssetType
from src.models.transaction import Transaction, TransactionSource
from src.models.category import Category, CategoryType
from src.services.category_service import CategoryService


class AssetService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.category_service = CategoryService(session)

    async def get_user_assets(self, user_id: int) -> List[AssetAccount]:
        """Fetch all active asset accounts for user."""
        res = await self.session.scalars(
            select(AssetAccount)
            .where(AssetAccount.user_id == user_id, AssetAccount.is_active == True)
            .order_by(AssetAccount.created_at.desc())
        )
        return list(res.all())

    async def get_or_create_default_asset(
        self,
        user_id: int,
        asset_type: AssetType = AssetType.deposit,
        currency: str = "KZT",
        name: Optional[str] = None
    ) -> AssetAccount:
        """Find an existing asset of matching type/currency or create a sensible default."""
        res = await self.session.scalars(
            select(AssetAccount).where(
                AssetAccount.user_id == user_id,
                AssetAccount.type == asset_type,
                AssetAccount.currency == currency,
                AssetAccount.is_active == True
            )
        )
        account = res.first()
        if not account:
            if not name:
                if asset_type == AssetType.deposit:
                    name = "Банковский депозит"
                elif asset_type == AssetType.currency:
                    name = f"Наличные {currency}"
                elif asset_type == AssetType.savings:
                    name = "Копилка"
                else:
                    name = "Инвестиционный счёт"
            account = AssetAccount(
                user_id=user_id,
                name=name,
                type=asset_type,
                currency=currency,
                balance=0.0
            )
            self.session.add(account)
            await self.session.flush()
        return account

    async def create_asset(
        self,
        user_id: int,
        name: str,
        asset_type: AssetType,
        currency: str = "KZT",
        initial_balance: float = 0.0,
        interest_rate: Optional[float] = None
    ) -> AssetAccount:
        account = AssetAccount(
            user_id=user_id,
            name=name.strip(),
            type=asset_type,
            currency=currency.upper().strip(),
            balance=initial_balance,
            interest_rate=interest_rate
        )
        self.session.add(account)
        await self.session.commit()
        await self.session.refresh(account)
        return account

    async def deposit_to_asset(
        self,
        user_id: int,
        asset_id: uuid.UUID,
        amount: float,
        note: Optional[str] = None
    ) -> AssetAccount:
        """Transfer funds from main balance into asset account."""
        account = await self.session.get(AssetAccount, asset_id)
        if not account or account.user_id != user_id:
            raise ValueError("Asset account not found")

        account.balance = float(Decimal(str(account.balance)) + Decimal(str(amount)))

        cats = await self.category_service.get_categories(user_id, CategoryType.transfer_out)
        cat = cats[0] if cats else None
        if not cat:
            cat = Category(name="Депозит и вклады", type=CategoryType.transfer_out, is_system=True)
            self.session.add(cat)
            await self.session.flush()

        tx = Transaction(
            user_id=user_id,
            category_id=cat.id,
            asset_account_id=account.id,
            amount=amount,
            type=CategoryType.transfer_out,
            item_name=f"Пополнение: {account.name}",
            raw_text=note,
            source=TransactionSource.manual
        )
        self.session.add(tx)
        await self.session.commit()
        await self.session.refresh(account)
        return account

    async def withdraw_from_asset(
        self,
        user_id: int,
        asset_id: uuid.UUID,
        amount: float,
        note: Optional[str] = None
    ) -> AssetAccount:
        """Withdraw funds from asset into main liquid balance."""
        account = await self.session.get(AssetAccount, asset_id)
        if not account or account.user_id != user_id:
            raise ValueError("Asset account not found")

        account.balance = float(Decimal(str(account.balance)) - Decimal(str(amount)))

        cats = await self.category_service.get_categories(user_id, CategoryType.transfer_in)
        cat = cats[0] if cats else None
        if not cat:
            cat = Category(name="Снятие с депозита", type=CategoryType.transfer_in, is_system=True)
            self.session.add(cat)
            await self.session.flush()

        tx = Transaction(
            user_id=user_id,
            category_id=cat.id,
            asset_account_id=account.id,
            amount=amount,
            type=CategoryType.transfer_in,
            item_name=f"Снятие: {account.name}",
            raw_text=note,
            source=TransactionSource.manual
        )
        self.session.add(tx)
        await self.session.commit()
        await self.session.refresh(account)
        return account

    async def get_portfolio_summary(self, user_id: int) -> Dict[str, Any]:
        """Aggregate total net worth: liquid balance + deposits + currencies."""
        accounts = await self.get_user_assets(user_id)
        user = await self.session.get(User, user_id)
        base_currency = user.currency if user else "KZT"

        approx_rates_to_kzt = {"KZT": 1.0, "USD": 500.0, "EUR": 540.0, "RUB": 5.3}
        base_rate_to_kzt = approx_rates_to_kzt.get(base_currency, 1.0)

        total_deposits_base = Decimal("0")
        total_currency_base = Decimal("0")
        account_list = []

        for acc in accounts:
            bal = Decimal(str(acc.balance or 0))
            kzt_equiv = bal * Decimal(str(approx_rates_to_kzt.get(acc.currency, 1.0)))
            converted_bal = kzt_equiv / Decimal(str(base_rate_to_kzt))

            if acc.type == AssetType.currency:
                total_currency_base += converted_bal
            else:
                total_deposits_base += converted_bal

            account_list.append({
                "id": str(acc.id),
                "name": acc.name,
                "type": acc.type.value if hasattr(acc.type, "value") else str(acc.type),
                "currency": acc.currency,
                "balance": float(bal),
                "interest_rate": float(acc.interest_rate) if acc.interest_rate else None,
                "converted_balance": float(round(converted_bal, 2))
            })

        total_assets_base = total_deposits_base + total_currency_base

        return {
            "base_currency": base_currency,
            "total_deposits": float(round(total_deposits_base, 2)),
            "total_currencies": float(round(total_currency_base, 2)),
            "total_assets": float(round(total_assets_base, 2)),
            "accounts": account_list
        }
