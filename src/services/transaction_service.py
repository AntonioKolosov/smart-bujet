from decimal import Decimal
from typing import Optional, Tuple, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.user import User
from src.models.category import Category, CategoryType
from src.models.transaction import Transaction, TransactionSource
from src.models.alias import UserItemAlias
from src.core.exceptions import InvalidTransactionAmountError, TransactionParseError
from src.services.parser_service import ParserService
from src.services.category_service import CategoryService
from src.services.ai_service import AIService
from src.services.discount_service import DiscountDistributor


class TransactionService:
    def __init__(self, session: AsyncSession, ai_service: Optional[AIService] = None):
        self.session = session
        self.ai_service = ai_service or AIService()
        self.category_service = CategoryService(session)

    async def _get_alias_category(self, user_id: int, item_name: str) -> Optional[Category]:
        """Local alias lookup (10-15 ms) without sending requests to Gemini."""
        normalized = item_name.strip().lower()
        query = select(UserItemAlias).where(
            UserItemAlias.user_id == user_id,
            UserItemAlias.item_name_normalized == normalized
        )
        alias = await self.session.scalar(query)
        if alias:
            alias.usage_count += 1
            return await self.session.get(Category, alias.category_id)
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
        """Find category by name or fallback to first available category."""
        cat = await self.category_service.find_by_name(category_name, cat_type, user_id)
        if not cat:
            cat = await self.category_service.find_by_name(category_name, None, user_id)
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

            category = await self._get_alias_category(user_id, normalized_name)
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
            raw_name = item.get("item_name") or last_raw_text or "Расход"
            normalized_name = ParserService.normalize_item_name(raw_name)
            cat_type = CategoryType(item.get("type", "expense"))

            category = await self._get_alias_category(user_id, normalized_name)
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

            category = await self._get_alias_category(user_id, normalized_name)
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

