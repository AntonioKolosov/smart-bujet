from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, Tuple, List
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.user import User
from src.models.category import Category, CategoryType
from src.models.transaction import Transaction, TransactionSource
from src.models.alias import UserItemAlias
from src.models.asset import AssetAccount, AssetType
from src.core.exceptions import InvalidTransactionAmountError, TransactionParseError
from src.services.parser_service import ParserService
from src.services.category_service import CategoryService
from src.services.asset_service import AssetService
from src.services.ai_service import AIService
from src.services.discount_service import DiscountDistributor


class TransactionService:
    def __init__(self, session: AsyncSession, ai_service: Optional[AIService] = None):
        self.session = session
        self.ai_service = ai_service or AIService()
        self.category_service = CategoryService(session)
        self.asset_service = AssetService(session)

    async def _get_alias_category(
        self,
        user_id: int,
        item_name: str,
        cat_type: Optional[CategoryType] = None
    ) -> Optional[Category]:
        """Local alias lookup (10-15 ms) without sending requests to Gemini."""
        normalized = item_name.strip().lower()
        query = select(UserItemAlias).where(
            UserItemAlias.user_id == user_id,
            UserItemAlias.item_name_normalized == normalized
        )
        alias = await self.session.scalar(query)
        if alias:
            cat = await self.session.get(Category, alias.category_id)
            if cat and (cat_type is None or cat.type == cat_type):
                alias.usage_count += 1
                return cat
        return None

    async def _save_alias(self, user_id: int, item_name: str, category_id: int) -> None:
        """Cache user item alias for future fast lookups."""
        normalized = item_name.strip().lower()
        query = select(UserItemAlias).where(
            UserItemAlias.user_id == user_id,
            UserItemAlias.item_name_normalized == normalized
        )
        alias = await self.session.scalar(query)
        if alias:
            alias.category_id = category_id
            alias.usage_count += 1
        else:
            new_alias = UserItemAlias(
                user_id=user_id,
                item_name_normalized=normalized,
                category_id=category_id,
                usage_count=1
            )
            self.session.add(new_alias)

    async def _resolve_category(
        self,
        category_name: str,
        cat_type: CategoryType,
        user_id: int
    ) -> Category:
        """Find category by name strictly respecting cat_type, or fallback to first category of that type."""
        cat = await self.category_service.find_by_name(category_name, cat_type, user_id)
        if not cat:
            categories = await self.category_service.get_categories(user_id, cat_type)
            cat = categories[0] if categories else None
        return cat

    async def process_text(self, user_id: int, text: str) -> List[Transaction]:
        """
        Multi-item capable text transaction processing:
        1. Fast Regex parsing (single item)
        2. Gemini AI fallback (multi-item batch or uncached single item)
        """
        user = await self.session.get(User, user_id)
        family_group_id = user.family_group_id if user else None

        parsed = ParserService.parse_text(text)
        raw_items: List[dict] = []
        discount_percent = None
        discount_amount = None
        total_paid = None

        if parsed:
            amount, item_name = parsed
            raw_items = [{"amount": amount, "item_name": item_name, "type": "expense", "category": None}]
        else:
            available_cats = await self.category_service.get_categories(user_id)
            cat_names = list({c.name for c in available_cats})
            payload = await self.ai_service.classify_text(text, cat_names)
            raw_items = payload.get("items", [])
            discount_percent = payload.get("discount_percent")
            discount_amount = payload.get("discount_amount")
            total_paid = payload.get("total_paid")

        if not raw_items:
            raise TransactionParseError("Could not parse transaction from message")

        raw_items = DiscountDistributor.distribute(
            raw_items,
            discount_percent=discount_percent,
            discount_amount=discount_amount,
            total_paid=total_paid,
        )

        transactions: List[Transaction] = []
        for item in raw_items:
            try:
                amt = Decimal(str(item.get("amount", 0) or 0))
            except Exception:
                amt = Decimal("0")

            if amt <= Decimal("0"):
                continue

            raw_name = item.get("item_name") or text
            normalized_name = ParserService.normalize_item_name(raw_name)
            cat_type = CategoryType(item.get("type", "expense"))

            category = await self._get_alias_category(user_id, normalized_name, cat_type)
            if not category and item.get("category"):
                category = await self._resolve_category(item["category"], cat_type, user_id)
            if not category:
                cats = await self.category_service.get_categories(user_id, cat_type)
                category = cats[0]

            orig_amt = item.get("original_amount")
            disc_amt = item.get("discount_amount")

            asset_account_id = None
            asset_amt = item.get("asset_amount")
            ex_rate = item.get("exchange_rate")

            if cat_type in (CategoryType.transfer_out, CategoryType.transfer_in):
                target_currency = item.get("target_currency", "KZT")
                target_type = AssetType.currency if target_currency != "KZT" else AssetType.deposit
                asset_acc = await self.asset_service.get_or_create_default_asset(
                    user_id=user_id,
                    asset_type=target_type,
                    currency=target_currency
                )
                asset_account_id = asset_acc.id
                delta = Decimal(str(asset_amt if asset_amt is not None else amt))
                if cat_type == CategoryType.transfer_out:
                    asset_acc.balance = float(Decimal(str(asset_acc.balance or 0)) + delta)
                else:
                    asset_acc.balance = float(Decimal(str(asset_acc.balance or 0)) - delta)

            tx = Transaction(
                user_id=user_id,
                family_group_id=family_group_id,
                category_id=category.id,
                amount=float(amt),
                original_amount=float(orig_amt) if orig_amt is not None else None,
                discount_amount=float(disc_amt) if disc_amt is not None else None,
                type=cat_type,
                asset_account_id=asset_account_id,
                asset_amount=float(asset_amt) if asset_amt is not None else None,
                exchange_rate=float(ex_rate) if ex_rate is not None else None,
                item_name=normalized_name,
                raw_text=text,
                source=TransactionSource.text,
            )
            tx.category = category
            self.session.add(tx)
            await self._save_alias(user_id, normalized_name, category.id)
            transactions.append(tx)

        if not transactions:
            raise InvalidTransactionAmountError("Amount must be greater than 0", raw_text=text)

        await self.session.commit()
        return transactions

    async def process_voice(
        self,
        user_id: int,
        audio_bytes: bytes,
        mime_type: str = "audio/ogg"
    ) -> List[Transaction]:
        """Process voice message in-memory without saving .ogg to disk."""
        user = await self.session.get(User, user_id)
        family_group_id = user.family_group_id if user else None

        available_cats = await self.category_service.get_categories(user_id)
        cat_names = list({c.name for c in available_cats})

        payload = await self.ai_service.parse_voice(audio_bytes, mime_type, cat_names)
        raw_items = payload.get("items", [])
        if not raw_items:
            raise TransactionParseError("Could not parse voice transaction")

        raw_items = DiscountDistributor.distribute(
            raw_items,
            discount_percent=payload.get("discount_percent"),
            discount_amount=payload.get("discount_amount"),
            total_paid=payload.get("total_paid"),
        )

        transactions: List[Transaction] = []
        last_raw_text = None

        for item in raw_items:
            try:
                amt = Decimal(str(item.get("amount", 0) or 0))
            except Exception:
                amt = Decimal("0")

            if amt <= Decimal("0"):
                continue

            last_raw_text = item.get("raw_text")
            cat_type = CategoryType(item.get("type", "expense"))
            fallback_name = "Доход" if cat_type == CategoryType.income else ("Перевод" if "transfer" in cat_type.value else "Расход")
            raw_name = item.get("item_name") or last_raw_text or fallback_name
            normalized_name = ParserService.normalize_item_name(raw_name)

            category = await self._get_alias_category(user_id, normalized_name, cat_type)
            if not category and item.get("category"):
                category = await self._resolve_category(item["category"], cat_type, user_id)
            if not category:
                cats = await self.category_service.get_categories(user_id, cat_type)
                category = cats[0]

            orig_amt = item.get("original_amount")
            disc_amt = item.get("discount_amount")

            asset_account_id = None
            asset_amt = item.get("asset_amount")
            ex_rate = item.get("exchange_rate")

            if cat_type in (CategoryType.transfer_out, CategoryType.transfer_in):
                target_currency = item.get("target_currency", "KZT")
                target_type = AssetType.currency if target_currency != "KZT" else AssetType.deposit
                asset_acc = await self.asset_service.get_or_create_default_asset(
                    user_id=user_id,
                    asset_type=target_type,
                    currency=target_currency
                )
                asset_account_id = asset_acc.id
                delta = Decimal(str(asset_amt if asset_amt is not None else amt))
                if cat_type == CategoryType.transfer_out:
                    asset_acc.balance = float(Decimal(str(asset_acc.balance or 0)) + delta)
                else:
                    asset_acc.balance = float(Decimal(str(asset_acc.balance or 0)) - delta)

            tx = Transaction(
                user_id=user_id,
                family_group_id=family_group_id,
                category_id=category.id,
                amount=float(amt),
                original_amount=float(orig_amt) if orig_amt is not None else None,
                discount_amount=float(disc_amt) if disc_amt is not None else None,
                type=cat_type,
                asset_account_id=asset_account_id,
                asset_amount=float(asset_amt) if asset_amt is not None else None,
                exchange_rate=float(ex_rate) if ex_rate is not None else None,
                item_name=normalized_name,
                raw_text=last_raw_text,
                source=TransactionSource.voice,
            )
            tx.category = category
            self.session.add(tx)
            await self._save_alias(user_id, normalized_name, category.id)
            transactions.append(tx)

        if not transactions:
            raise InvalidTransactionAmountError("Amount must be greater than 0", raw_text=last_raw_text)

        await self.session.commit()
        return transactions

    async def process_receipt_photo(
        self,
        user_id: int,
        image_bytes: bytes,
        mime_type: str = "image/jpeg"
    ) -> List[Transaction]:
        """Process receipt photo in-memory without saving image to disk."""
        user = await self.session.get(User, user_id)
        family_group_id = user.family_group_id if user else None

        available_cats = await self.category_service.get_categories(user_id)
        cat_names = list({c.name for c in available_cats})

        payload = await self.ai_service.parse_receipt_photo(image_bytes, mime_type, cat_names)
        raw_items = payload.get("items", [])
        if not raw_items:
            raise TransactionParseError("Could not parse receipt photo")

        raw_items = DiscountDistributor.distribute(
            raw_items,
            discount_percent=payload.get("discount_percent"),
            discount_amount=payload.get("discount_amount"),
            total_paid=payload.get("total_paid"),
        )

        transactions: List[Transaction] = []
        for item in raw_items:
            try:
                amt = Decimal(str(item.get("amount", 0) or 0))
            except Exception:
                amt = Decimal("0")

            if amt <= Decimal("0"):
                continue

            raw_name = item.get("item_name") or "Чек"
            normalized_name = ParserService.normalize_item_name(raw_name)
            cat_type = CategoryType(item.get("type", "expense"))

            category = await self._get_alias_category(user_id, normalized_name, cat_type)
            if not category and item.get("category"):
                category = await self._resolve_category(item["category"], cat_type, user_id)
            if not category:
                cats = await self.category_service.get_categories(user_id, cat_type)
                category = cats[0]

            orig_amt = item.get("original_amount")
            disc_amt = item.get("discount_amount")

            tx = Transaction(
                user_id=user_id,
                family_group_id=family_group_id,
                category_id=category.id,
                amount=float(amt),
                original_amount=float(orig_amt) if orig_amt is not None else None,
                discount_amount=float(disc_amt) if disc_amt is not None else None,
                type=cat_type,
                item_name=normalized_name,
                raw_text="[Фото чека]",
                source=TransactionSource.photo,
            )
            tx.category = category
            self.session.add(tx)
            await self._save_alias(user_id, normalized_name, category.id)
            transactions.append(tx)

        if not transactions:
            raise InvalidTransactionAmountError("Amount must be greater than 0")

        await self.session.commit()
        return transactions

    async def get_user_balance(self, user_id: int) -> dict:
        """Calculate live account balance and monthly metrics."""
        user = await self.session.get(User, user_id)
        initial = Decimal(str(user.initial_balance or 0)) if user and user.initial_balance is not None else Decimal(0)

        now = datetime.now(timezone.utc)
        start_month = datetime(now.year, now.month, 1, 0, 0, 0, tzinfo=timezone.utc)
        if now.month == 12:
            next_month = datetime(now.year + 1, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        else:
            next_month = datetime(now.year, now.month + 1, 1, 0, 0, 0, tzinfo=timezone.utc)

        MONTH_NAMES_RU = [
            "", "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
            "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"
        ]
        month_label = f"{MONTH_NAMES_RU[now.month]} {now.year}"

        income_sum = await self.session.scalar(
            select(func.coalesce(func.sum(Transaction.amount), 0))
            .where(Transaction.user_id == user_id, Transaction.type == CategoryType.income)
        ) or 0

        expense_sum = await self.session.scalar(
            select(func.coalesce(func.sum(Transaction.amount), 0))
            .where(Transaction.user_id == user_id, Transaction.type == CategoryType.expense)
        ) or 0

        transfer_out_sum = await self.session.scalar(
            select(func.coalesce(func.sum(Transaction.amount), 0))
            .where(Transaction.user_id == user_id, Transaction.type == CategoryType.transfer_out)
        ) or 0

        transfer_in_sum = await self.session.scalar(
            select(func.coalesce(func.sum(Transaction.amount), 0))
            .where(Transaction.user_id == user_id, Transaction.type == CategoryType.transfer_in)
        ) or 0

        month_expense = await self.session.scalar(
            select(func.coalesce(func.sum(Transaction.amount), 0))
            .where(
                Transaction.user_id == user_id,
                Transaction.type == CategoryType.expense,
                Transaction.transaction_date >= start_month,
                Transaction.transaction_date < next_month,
            )
        ) or 0

        month_income = await self.session.scalar(
            select(func.coalesce(func.sum(Transaction.amount), 0))
            .where(
                Transaction.user_id == user_id,
                Transaction.type == CategoryType.income,
                Transaction.transaction_date >= start_month,
                Transaction.transaction_date < next_month,
            )
        ) or 0

        current_balance = (
            initial
            + Decimal(str(income_sum))
            - Decimal(str(expense_sum))
            - Decimal(str(transfer_out_sum))
            + Decimal(str(transfer_in_sum))
        )
        return {
            "initial_balance": float(initial),
            "total_income": float(income_sum),
            "total_expense": float(expense_sum),
            "month_income": float(month_income),
            "month_expense": float(month_expense),
            "month_period_name": month_label,
            "current_balance": float(current_balance),
            "currency": user.currency if user else "KZT",
        }

