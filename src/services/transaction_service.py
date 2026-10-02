from decimal import Decimal
from typing import Optional, Tuple
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

    async def process_text(self, user_id: int, text: str) -> Transaction:
        """
        Two-level parsing:
        1. Fast Regex parsing
        2. Local alias lookup (10-15 ms)
        3. Gemini AI fallback if alias not found
        """
        user = await self.session.get(User, user_id)
        family_group_id = user.family_group_id if user else None

        # Level 1: Regex parse amount and item name
        parsed = ParserService.parse_text(text)
        amount = parsed[0] if parsed else None
        item_name = parsed[1] if parsed else text.strip()

        # Level 2: Local user alias cache lookup
        category = None
        cat_type = CategoryType.expense
        if item_name:
            category = await self._get_alias_category(user_id, item_name)
            if category:
                cat_type = category.type

        # Level 3: Fallback to Gemini 2.5 Flash if category not found in cache or amount missing
        if not category or amount is None:
            available_cats = await self.category_service.get_categories(user_id)
            cat_names = list({c.name for c in available_cats})

            ai_result = await self.ai_service.classify_text(text, cat_names)
            ai_cat_name = ai_result.get("category") or "Обязательные расходы"
            cat_type = CategoryType(ai_result.get("type", "expense"))

            if not category:
                category = await self._resolve_category(ai_cat_name, cat_type, user_id)

            if amount is None and ai_result.get("amount"):
                try:
                    amount = Decimal(str(ai_result["amount"]))
                except Exception:
                    amount = Decimal("0")

            if ai_result.get("item_name") and (not item_name or item_name == text.strip()):
                item_name = ai_result["item_name"]

        if not amount or amount <= Decimal("0"):
            raise InvalidTransactionAmountError("Amount must be greater than 0", raw_text=text)

        if not category:
            cats = await self.category_service.get_categories(user_id, cat_type)
            category = cats[0]

        # Save transaction
        tx = Transaction(
            user_id=user_id,
            family_group_id=family_group_id,
            category_id=category.id,
            amount=float(amount),
            type=cat_type,
            item_name=item_name or text,
            raw_text=text,
            source=TransactionSource.text
        )
        self.session.add(tx)

        # Update local alias cache for future instant lookup
        if item_name:
            await self._save_alias(user_id, item_name, category.id)

        await self.session.commit()
        tx.category = category
        return tx

    async def process_voice(
        self,
        user_id: int,
        audio_bytes: bytes,
        mime_type: str = "audio/ogg"
    ) -> Transaction:
        """Process voice message in-memory without saving .ogg to disk."""
        user = await self.session.get(User, user_id)
        family_group_id = user.family_group_id if user else None

        available_cats = await self.category_service.get_categories(user_id)
        cat_names = list({c.name for c in available_cats})

        ai_result = await self.ai_service.parse_voice(audio_bytes, mime_type, cat_names)
        ai_cat_name = ai_result.get("category") or "Обязательные расходы"
        cat_type = CategoryType(ai_result.get("type", "expense"))
        category = await self._resolve_category(ai_cat_name, cat_type, user_id)

        try:
            amount = Decimal(str(ai_result.get("amount", 0) or 0))
        except Exception:
            amount = Decimal("0")

        if amount <= Decimal("0"):
            raise InvalidTransactionAmountError("Amount must be greater than 0", raw_text=raw_text)

        item_name = ai_result.get("item_name") or raw_text or "Расход"

        tx = Transaction(
            user_id=user_id,
            family_group_id=family_group_id,
            category_id=category.id,
            amount=float(amount),
            type=cat_type,
            item_name=item_name,
            raw_text=raw_text,
            source=TransactionSource.voice
        )
        self.session.add(tx)
        if item_name:
            await self._save_alias(user_id, item_name, category.id)

        await self.session.commit()
        tx.category = category
        return tx

    async def process_receipt_photo(
        self,
        user_id: int,
        image_bytes: bytes,
        mime_type: str = "image/jpeg"
    ) -> Transaction:
        """Process receipt photo in-memory without saving image to disk."""
        user = await self.session.get(User, user_id)
        family_group_id = user.family_group_id if user else None

        available_cats = await self.category_service.get_categories(user_id)
        cat_names = list({c.name for c in available_cats})

        ai_result = await self.ai_service.parse_receipt_photo(image_bytes, mime_type, cat_names)
        ai_cat_name = ai_result.get("category") or "Продукты"
        cat_type = CategoryType(ai_result.get("type", "expense"))
        category = await self._resolve_category(ai_cat_name, cat_type, user_id)

        try:
            amount = Decimal(str(ai_result.get("amount", 0) or 0))
        except Exception:
            amount = Decimal("0")

        if amount <= Decimal("0"):
            raise InvalidTransactionAmountError("Amount must be greater than 0")

        item_name = ai_result.get("item_name") or "Чек"

        tx = Transaction(
            user_id=user_id,
            family_group_id=family_group_id,
            category_id=category.id,
            amount=float(amount),
            type=cat_type,
            item_name=item_name,
            raw_text="[Фото чека]",
            source=TransactionSource.photo
        )
        self.session.add(tx)
        if item_name:
            await self._save_alias(user_id, item_name, category.id)

        await self.session.commit()
        tx.category = category
        return tx

