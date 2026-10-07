import uuid
import re
import asyncio
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from sqlalchemy import select, func
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from src.models.user import User
from src.models.category import Category, CategoryType
from src.models.transaction import Transaction, TransactionSource
from src.models.alias import UserItemAlias
from src.models.asset import AssetAccount, AssetType
from src.models.credit import CreditAccount
from src.schemas.transaction import TransactionCreate, TransactionUpdate
from src.core.exceptions import InvalidTransactionAmountError, TransactionParseError, OffTopicMessageError
from src.services.parser_service import ParserService
from src.services.category_service import CategoryService
from src.services.asset_service import AssetService
from src.services.credit_service import CreditService
from src.services.ai_service import AIService
from src.services.dynamic_context_service import DynamicContextService
from src.services.discount_service import DiscountDistributor
from src.bot.messages import format_amount

logger = logging.getLogger(__name__)

PARTNER_TRANSFER_REGEX = re.compile(
    r"\b(?:партнер[а-я]*|жен[а-я]*|муж[а-я]*|супруг[а-я]*|половинк[а-я]*)\b",
    re.IGNORECASE
)


class BatchCategoryResolver:
    """
    Unified in-memory resolver and memoizer for batch transaction processing.
    Eliminates read and write N+1 database queries across text, voice, and photo processing.
    """
    def __init__(self, service: "TransactionService", user_id: int):
        self.service = service
        self.user_id = user_id
        self.alias_cache: dict[tuple[str, CategoryType | None], Category | None] = {}
        self.resolve_cache: dict[tuple[str, CategoryType], Category | None] = {}
        self.fallback_cache: dict[CategoryType, Category | None] = {}
        self.saved_aliases: set[str] = set()

    async def resolve(
        self,
        item: dict,
        normalized_name: str,
        cat_type: CategoryType
    ) -> Category | None:
        alias_key = (normalized_name, cat_type)
        if alias_key not in self.alias_cache:
            self.alias_cache[alias_key] = await self.service._get_alias_category(
                self.user_id, normalized_name, cat_type
            )
        category = self.alias_cache[alias_key]

        if not category and item.get("category"):
            resolve_key = (item["category"], cat_type)
            if resolve_key not in self.resolve_cache:
                self.resolve_cache[resolve_key] = await self.service._resolve_category(
                    item["category"], cat_type, self.user_id
                )
            category = self.resolve_cache[resolve_key]

        if not category:
            if cat_type not in self.fallback_cache:
                cats = await self.service.category_service.get_categories(self.user_id, cat_type)
                safe_cats = [
                    c for c in cats
                    if c.name not in ("Денежный перевод", "Депозит и вклады", "Покупка валюты", "Погашение кредита", "Получение кредита", "Снятие с депозита", "Продажа валюты")
                ]
                self.fallback_cache[cat_type] = safe_cats[0] if safe_cats else (cats[0] if cats else None)
            category = self.fallback_cache[cat_type]

        return category

    async def record_alias(self, normalized_name: str, category: Category | None) -> None:
        if not category:
            return
        # Do not record alias for special transfer/credit/deposit categories unless explicitly intended
        if category.name in ("Денежный перевод", "Депозит и вклады", "Покупка валюты", "Погашение кредита", "Получение кредита"):
            return
        alias_key = (normalized_name, category.type)
        self.alias_cache[alias_key] = category

        if normalized_name not in self.saved_aliases:
            await self.service._save_alias(self.user_id, normalized_name, category.id)
            self.saved_aliases.add(normalized_name)


class TransactionService:
    def __init__(self, session: AsyncSession, ai_service: AIService | None = None):
        self.session = session
        self.ai_service = ai_service or AIService()
        self.category_service = CategoryService(session)
        self.asset_service = AssetService(session)
        self.credit_service = CreditService(session)
        self.dynamic_service = DynamicContextService(session)

    async def _detect_family_partner(self, user: User, text: str, item_name: str) -> User | None:
        """Detect if the transaction is directed to the user's family partner."""
        if not user.family_group_id:
            return None

        partner_query = select(User).where(
            User.family_group_id == user.family_group_id,
            User.id != user.id
        )
        partner = await self.session.scalar(partner_query)
        if not partner:
            return None

        combined_text = f"{text or ''} {item_name or ''}".lower()
        if PARTNER_TRANSFER_REGEX.search(combined_text):
            return partner

        if partner.first_name and len(partner.first_name.strip()) >= 2:
            fname = partner.first_name.strip().lower()
            stem = fname[:-1] if len(fname) >= 4 and fname[-1] in "аяеиуыо" else fname
            if fname in combined_text or (len(stem) >= 3 and stem in combined_text):
                return partner

        if partner.username and len(partner.username.strip()) >= 2:
            if partner.username.strip().lower().lstrip("@") in combined_text:
                return partner

        return None

    async def _handle_intra_family_mirror(
        self,
        sender: User | None,
        primary_tx: Transaction,
        context_text: str | None = None
    ) -> User | None:
        """
        Creates mirror income transaction for family partner if primary transaction is an expense transfer to partner.
        Returns the partner User if mirrored, else None.
        """
        if not sender or not sender.family_group_id:
            return None
        if not (primary_tx.category and primary_tx.category.name == "Денежный перевод" and primary_tx.type == CategoryType.expense):
            return None

        partner = await self._detect_family_partner(sender, context_text or "", primary_tx.item_name or "")
        if not partner:
            return None

        action_partner_name = partner.first_name or partner.username or "Партнёр"
        primary_tx.item_name = f"Перевод: {action_partner_name}"

        mirror_cat = await self._resolve_category("Денежный перевод", CategoryType.income, partner.id)
        sender_name = sender.first_name or sender.username or "Партнёр"
        raw_msg = f"Перевод от {sender_name}: {context_text or ''}".strip()

        tx_mirror = Transaction(
            user_id=partner.id,
            family_group_id=sender.family_group_id,
            category_id=mirror_cat.id,
            amount=primary_tx.amount,
            type=CategoryType.income,
            item_name=f"Перевод от: {sender_name}",
            raw_text=raw_msg,
            source=TransactionSource.manual,
        )
        tx_mirror.category = mirror_cat
        self.session.add(tx_mirror)

        await self.session.flush()
        primary_tx.related_transaction_id = tx_mirror.id
        tx_mirror.related_transaction_id = primary_tx.id

        return partner

    async def _get_alias_category(
        self,
        user_id: int,
        item_name: str,
        cat_type: CategoryType | None = None
    ) -> Category | None:
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

    async def _handle_asset_transfer(
        self,
        user_id: int,
        user: User | None,
        item: dict,
        cat_type: CategoryType,
        amt: Decimal,
        asset_amt: Any | None,
        context_text: str | None = None
    ) -> tuple[uuid.UUID, str, AssetAccount]:
        raw_curr = item.get("target_currency")
        target_currency = (
            raw_curr.strip().upper()
            if raw_curr and str(raw_curr).strip().upper() not in ("NONE", "NULL", "")
            else None
        ) or (user.currency if user else "KZT")

        target_type = AssetType.deposit

        target_asset_name = item.get("target_asset_name")
        if target_asset_name and any(b in target_asset_name.lower() for b in ["покупка", "валюты", "none", "null"]):
            target_asset_name = None

        asset_id_hint = item.get("asset_account_id")

        asset_acc = await self.asset_service.resolve_asset_account(
            user_id=user_id,
            target_name=target_asset_name,
            target_type=target_type,
            target_currency=target_currency,
            asset_id_hint=asset_id_hint
        )
        if not asset_acc:
            safe_name = target_asset_name
            if not safe_name and target_currency != (user.currency if user else "KZT"):
                safe_name = f"Депозит {target_currency}"
            asset_acc = await self.asset_service.get_or_create_default_asset(
                user_id=user_id,
                asset_type=target_type,
                currency=target_currency,
                name=safe_name
            )

        delta = Decimal(str(asset_amt if asset_amt is not None else amt))
        if cat_type == CategoryType.transfer_out:
            asset_acc.balance = float(Decimal(str(asset_acc.balance or 0)) + delta)
        else:
            asset_acc.balance = float(Decimal(str(asset_acc.balance or 0)) - delta)

        return asset_acc.id, asset_acc.name, asset_acc

    async def process_text(self, user_id: int, text: str) -> list[Transaction]:
        """
        Multi-item capable text transaction processing:
        1. Fast Regex parsing (single item)
        2. Gemini AI fallback (multi-item batch or uncached single item)
        """
        user = await self.session.get(User, user_id)
        family_group_id = user.family_group_id if user else None

        parsed = ParserService.parse_text(text)
        raw_items: list[dict] = []
        discount_percent = None
        discount_amount = None
        total_paid = None

        if parsed:
            amount, item_name = parsed
            normalized_name = ParserService.normalize_item_name(item_name)
            # Only use fast-path if user already has an established alias for this item
            known_alias = await self._get_alias_category(user_id, normalized_name, CategoryType.expense)
            if known_alias:
                raw_items = [{"amount": amount, "item_name": normalized_name, "type": "expense", "category": known_alias.name}]

        if not raw_items:
            available_cats = await self.category_service.get_categories(user_id)
            cat_names = list({c.name for c in available_cats})
            accessible_assets = await self.asset_service.get_accessible_assets(user_id)
            assets_context = [
                {
                    "id": str(a.id),
                    "name": a.name,
                    "type": a.type.value if hasattr(a.type, "value") else str(a.type),
                    "currency": a.currency,
                }
                for a in accessible_assets
            ]
            user_credits = await self.credit_service.get_user_credits(user_id, active_only=True)
            credits_context = [
                {
                    "id": str(c.id),
                    "name": c.name,
                    "remaining_amount": float(c.remaining_amount),
                    "monthly_payment": float(c.monthly_payment) if c.monthly_payment is not None else None,
                    "currency": c.currency,
                }
                for c in user_credits
            ]
            few_shots = await self.dynamic_service.get_few_shots_for_query(text)
            few_shots_prompt = self.dynamic_service.format_few_shots_prompt(few_shots)
            payload = await self.ai_service.classify_text(
                text,
                cat_names,
                assets_context=assets_context,
                credits_context=credits_context,
                few_shots_prompt=few_shots_prompt
            )
            if payload.get("is_financial") is False:
                raise OffTopicMessageError("Сообщение не относится к финансовым операциям", raw_text=text)
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

        transactions: list[Transaction] = []

        resolver = BatchCategoryResolver(self, user_id)

        for item in raw_items:
            try:
                amt = Decimal(str(item.get("amount", 0) or 0))
            except Exception:
                amt = Decimal("0")

            # Service-level fallback: Credit Monthly Payment Auto-Fill
            credit_action = item.get("credit_action")
            is_repay = (credit_action == "repay" or item.get("category") == "Погашение кредита")
            if amt <= Decimal("0") and is_repay:
                target_name = item.get("target_credit_name") or item.get("item_name")
                hint_id = item.get("credit_account_id")
                resolved_c = await self.credit_service.resolve_credit_account(
                    user_id=user_id,
                    target_name=target_name,
                    credit_id_hint=hint_id
                )
                if resolved_c and resolved_c.monthly_payment and resolved_c.monthly_payment > 0:
                    amt = Decimal(str(resolved_c.monthly_payment))
                    item["amount"] = float(amt)
                    item["target_credit_name"] = resolved_c.name
                    item["credit_account_id"] = str(resolved_c.id)

            if amt <= Decimal("0"):
                continue

            raw_name = item.get("item_name") or text
            normalized_name = ParserService.normalize_item_name(raw_name)
            cat_type = CategoryType(item.get("type", "expense"))

            category = await resolver.resolve(item, normalized_name, cat_type)

            orig_amt = item.get("original_amount")
            disc_amt = item.get("discount_amount")

            asset_account_id = None
            credit_account_id = None
            asset_amt = item.get("asset_amount")
            ex_rate = item.get("exchange_rate")

            credit_action = item.get("credit_action")
            if credit_action == "take" or item.get("category") == "Получение кредита":
                credit_name = item.get("target_credit_name") or item.get("item_name") or "Кредит"
                if credit_name.lower().startswith("кредит:"):
                    credit_name = credit_name.split(":", 1)[1].strip()
                new_credit = await self.credit_service.create_credit(
                    user_id=user_id,
                    name=credit_name,
                    original_amount=amt,
                    currency=user.currency if user else "KZT",
                    auto_commit=False
                )
                credit_account_id = new_credit.id
                normalized_name = f"Кредит: {new_credit.name}"
            elif credit_action == "repay" or item.get("category") == "Погашение кредита":
                target_credit_name = item.get("target_credit_name") or item.get("item_name")
                credit_hint = item.get("credit_account_id")
                credit = await self.credit_service.resolve_credit_account(
                    user_id=user_id,
                    target_name=target_credit_name,
                    credit_id_hint=credit_hint
                )
                if credit:
                    updated_credit, was_closed = await self.credit_service.repay_credit(
                        user_id=user_id,
                        credit_id=credit.id,
                        amount=amt,
                        auto_commit=False
                    )
                    credit_account_id = credit.id
                    rem_str = f"{float(updated_credit.remaining_amount):,.2f}".replace(",", " ")
                    status_suffix = " (Закрыт! 🎉)" if was_closed else f" (Остаток: {rem_str} {updated_credit.currency})"
                    normalized_name = f"Погашение: {credit.name}{status_suffix}"

            asset_account_obj = None
            if cat_type in (CategoryType.transfer_out, CategoryType.transfer_in):
                if ex_rate and float(ex_rate) > 1 and asset_amt and abs(float(amt) - float(asset_amt)) < 1.0:
                    amt = Decimal(str(asset_amt)) * Decimal(str(ex_rate))

                asset_account_id, asset_acc_name, asset_account_obj = await self._handle_asset_transfer(
                    user_id=user_id,
                    user=user,
                    item=item,
                    cat_type=cat_type,
                    amt=amt,
                    asset_amt=asset_amt,
                    context_text=text
                )
                action_prefix = "Пополнение" if cat_type == CategoryType.transfer_out else "Снятие"
                normalized_name = f"{action_prefix}: {asset_acc_name}"

            tx = Transaction(
                user_id=user_id,
                family_group_id=family_group_id,
                category_id=category.id,
                amount=float(amt),
                original_amount=float(orig_amt) if orig_amt is not None else None,
                discount_amount=float(disc_amt) if disc_amt is not None else None,
                type=cat_type,
                asset_account_id=asset_account_id,
                credit_account_id=credit_account_id,
                asset_amount=float(asset_amt) if asset_amt is not None else None,
                exchange_rate=float(ex_rate) if ex_rate is not None else None,
                item_name=normalized_name,
                raw_text=text,
                source=TransactionSource.text,
            )
            tx.category = category
            if asset_account_obj:
                tx.asset_account = asset_account_obj
            self.session.add(tx)
            await resolver.record_alias(normalized_name, category)
            transactions.append(tx)

            # Check and handle intra-family transfer mirror
            await self._handle_intra_family_mirror(user, tx, text)

        if not transactions:
            raise InvalidTransactionAmountError("Amount must be greater than 0", raw_text=text)

        await self.session.commit()
        return transactions

    async def process_voice(
        self,
        user_id: int,
        audio_bytes: bytes,
        mime_type: str = "audio/ogg"
    ) -> list[Transaction]:
        """Process voice message in-memory without saving .ogg to disk."""
        user = await self.session.get(User, user_id)
        family_group_id = user.family_group_id if user else None

        available_cats = await self.category_service.get_categories(user_id)
        cat_names = list({c.name for c in available_cats})
        accessible_assets = await self.asset_service.get_accessible_assets(user_id)
        assets_context = [
            {
                "id": str(a.id),
                "name": a.name,
                "type": a.type.value if hasattr(a.type, "value") else str(a.type),
                "currency": a.currency,
            }
            for a in accessible_assets
        ]

        user_credits = await self.credit_service.get_user_credits(user_id, active_only=True)
        credits_context = [
            {
                "id": str(c.id),
                "name": c.name,
                "remaining_amount": float(c.remaining_amount),
                "monthly_payment": float(c.monthly_payment) if c.monthly_payment is not None else None,
                "currency": c.currency,
            }
            for c in user_credits
        ]

        few_shots = await self.dynamic_service.get_few_shots_for_query("голос")
        few_shots_prompt = self.dynamic_service.format_few_shots_prompt(few_shots)
        payload = await self.ai_service.parse_voice(
            audio_bytes,
            mime_type,
            cat_names,
            assets_context=assets_context,
            credits_context=credits_context,
            few_shots_prompt=few_shots_prompt
        )
        if payload.get("is_financial") is False:
            raise OffTopicMessageError("Голосовое сообщение не содержит финансовых операций", raw_text=None)
        raw_items = payload.get("items", [])
        if not raw_items:
            raise TransactionParseError("Could not parse voice transaction")

        raw_items = DiscountDistributor.distribute(
            raw_items,
            discount_percent=payload.get("discount_percent"),
            discount_amount=payload.get("discount_amount"),
            total_paid=payload.get("total_paid"),
        )

        transactions: list[Transaction] = []
        last_raw_text = None

        resolver = BatchCategoryResolver(self, user_id)

        for item in raw_items:
            try:
                amt = Decimal(str(item.get("amount", 0) or 0))
            except Exception:
                amt = Decimal("0")

            # Service-level fallback: Credit Monthly Payment Auto-Fill
            credit_action = item.get("credit_action")
            is_repay = (credit_action == "repay" or item.get("category") == "Погашение кредита")
            if amt <= Decimal("0") and is_repay:
                target_name = item.get("target_credit_name") or item.get("item_name")
                hint_id = item.get("credit_account_id")
                resolved_c = await self.credit_service.resolve_credit_account(
                    user_id=user_id,
                    target_name=target_name,
                    credit_id_hint=hint_id
                )
                if resolved_c and resolved_c.monthly_payment and resolved_c.monthly_payment > 0:
                    amt = Decimal(str(resolved_c.monthly_payment))
                    item["amount"] = float(amt)
                    item["target_credit_name"] = resolved_c.name
                    item["credit_account_id"] = str(resolved_c.id)

            if amt <= Decimal("0"):
                continue

            last_raw_text = item.get("raw_text")
            cat_type = CategoryType(item.get("type", "expense"))
            fallback_name = "Доход" if cat_type == CategoryType.income else ("Перевод" if "transfer" in cat_type.value else "Расход")
            raw_name = item.get("item_name") or last_raw_text or fallback_name
            normalized_name = ParserService.normalize_item_name(raw_name)

            category = await resolver.resolve(item, normalized_name, cat_type)

            orig_amt = item.get("original_amount")
            disc_amt = item.get("discount_amount")

            asset_account_id = None
            credit_account_id = None
            asset_amt = item.get("asset_amount")
            ex_rate = item.get("exchange_rate")

            credit_action = item.get("credit_action")
            if credit_action == "take" or item.get("category") == "Получение кредита":
                credit_name = item.get("target_credit_name") or item.get("item_name") or "Кредит"
                if credit_name.lower().startswith("кредит:"):
                    credit_name = credit_name.split(":", 1)[1].strip()
                new_credit = await self.credit_service.create_credit(
                    user_id=user_id,
                    name=credit_name,
                    original_amount=amt,
                    currency=user.currency if user else "KZT",
                    auto_commit=False
                )
                credit_account_id = new_credit.id
                normalized_name = f"Кредит: {new_credit.name}"
            elif credit_action == "repay" or item.get("category") == "Погашение кредита":
                target_credit_name = item.get("target_credit_name") or item.get("item_name")
                credit_hint = item.get("credit_account_id")
                credit = await self.credit_service.resolve_credit_account(
                    user_id=user_id,
                    target_name=target_credit_name,
                    credit_id_hint=credit_hint
                )
                if credit:
                    updated_credit, was_closed = await self.credit_service.repay_credit(
                        user_id=user_id,
                        credit_id=credit.id,
                        amount=amt,
                        auto_commit=False
                    )
                    credit_account_id = credit.id
                    rem_str = f"{float(updated_credit.remaining_amount):,.2f}".replace(",", " ")
                    status_suffix = " (Закрыт! 🎉)" if was_closed else f" (Остаток: {rem_str} {updated_credit.currency})"
                    normalized_name = f"Погашение: {credit.name}{status_suffix}"

            asset_account_obj = None
            if cat_type in (CategoryType.transfer_out, CategoryType.transfer_in):
                if ex_rate and float(ex_rate) > 1 and asset_amt and abs(float(amt) - float(asset_amt)) < 1.0:
                    amt = Decimal(str(asset_amt)) * Decimal(str(ex_rate))

                asset_account_id, asset_acc_name, asset_account_obj = await self._handle_asset_transfer(
                    user_id=user_id,
                    user=user,
                    item=item,
                    cat_type=cat_type,
                    amt=amt,
                    asset_amt=asset_amt,
                    context_text=last_raw_text
                )
                action_prefix = "Пополнение" if cat_type == CategoryType.transfer_out else "Снятие"
                normalized_name = f"{action_prefix}: {asset_acc_name}"

            tx = Transaction(
                user_id=user_id,
                family_group_id=family_group_id,
                category_id=category.id,
                amount=float(amt),
                original_amount=float(orig_amt) if orig_amt is not None else None,
                discount_amount=float(disc_amt) if disc_amt is not None else None,
                type=cat_type,
                asset_account_id=asset_account_id,
                credit_account_id=credit_account_id,
                asset_amount=float(asset_amt) if asset_amt is not None else None,
                exchange_rate=float(ex_rate) if ex_rate is not None else None,
                item_name=normalized_name,
                raw_text=last_raw_text,
                source=TransactionSource.voice,
            )
            tx.category = category
            if asset_account_obj:
                tx.asset_account = asset_account_obj
            self.session.add(tx)
            await resolver.record_alias(normalized_name, category)
            transactions.append(tx)

            # Check and handle intra-family transfer mirror
            await self._handle_intra_family_mirror(user, tx, last_raw_text)

        if not transactions:
            raise InvalidTransactionAmountError("Amount must be greater than 0", raw_text=last_raw_text)

        await self.session.commit()
        return transactions

    async def _build_transactions_from_receipt_payload(
        self,
        payload: dict[str, Any],
        user_id: int,
        family_group_id: Any,
        resolver: BatchCategoryResolver,
        fallback_index: int = 1
    ) -> tuple[list[Transaction], str]:
        raw_items = payload.get("items", [])
        if not raw_items:
            return [], ""

        est_type = str(payload.get("establishment_type") or "").lower()
        venue_name = payload.get("venue_name")
        dining_keywords = ("кафе", "cafe", "ресторан", "rest", "кофейн", "coffee", "бар", "bar", "pub", "паб", "додо", "burger", "пицц", "столов", "kfc", "mcdonald")
        is_dining = (
            est_type == "dining"
            or (venue_name and any(k in str(venue_name).lower() for k in dining_keywords))
            or (len(raw_items) > 1 and all(it.get("category") in ("Еда вне дома", "Кафе и рестораны") for it in raw_items))
        )

        receipt_title = ""
        if venue_name and str(venue_name).strip():
            receipt_title = str(venue_name).strip()

        if is_dining and len(raw_items) > 1:
            total_sum = Decimal(str(payload.get("total_paid") or 0))
            if total_sum <= Decimal("0"):
                total_sum = sum(Decimal(str(it.get("amount", 0) or 0)) for it in raw_items)

            display_name = f"Кафе: {venue_name.strip()}" if venue_name else "Поход в кафе"
            raw_items = [{
                "item_name": display_name,
                "category": "Еда вне дома",
                "type": "expense",
                "amount": float(total_sum)
            }]
            payload["discount_percent"] = None
            payload["discount_amount"] = None
            payload["total_paid"] = float(total_sum)

        raw_items = DiscountDistributor.distribute(
            raw_items,
            discount_percent=payload.get("discount_percent"),
            discount_amount=payload.get("discount_amount"),
            total_paid=payload.get("total_paid"),
        )

        transactions: list[Transaction] = []

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

            category = await resolver.resolve(item, normalized_name, cat_type)

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
            await resolver.record_alias(normalized_name, category)
            transactions.append(tx)

        if not receipt_title:
            if is_dining:
                receipt_title = "Кафе"
            elif len(transactions) == 1:
                receipt_title = transactions[0].item_name
            else:
                receipt_title = f"Чек {fallback_index}"

        return transactions, receipt_title

    async def process_receipt_photo(
        self,
        user_id: int,
        image_bytes: bytes,
        mime_type: str = "image/jpeg"
    ) -> list[Transaction]:
        """Process receipt photo in-memory without saving image to disk."""
        user = await self.session.get(User, user_id)
        family_group_id = user.family_group_id if user else None

        available_cats = await self.category_service.get_categories(user_id)
        cat_names = list({c.name for c in available_cats})

        payload = await self.ai_service.parse_receipt_photo(image_bytes, mime_type, cat_names)
        if payload.get("is_financial") is False:
            raise OffTopicMessageError("На фотографии не обнаружен кассовый чек", raw_text=None)
        if not payload.get("items"):
            raise TransactionParseError("Could not parse receipt photo")

        resolver = BatchCategoryResolver(self, user_id)
        transactions, _ = await self._build_transactions_from_receipt_payload(
            payload=payload,
            user_id=user_id,
            family_group_id=family_group_id,
            resolver=resolver,
            fallback_index=1
        )

        if not transactions:
            raise InvalidTransactionAmountError("Amount must be greater than 0")

        await self.session.commit()
        return transactions

    async def process_receipt_photos(
        self,
        user_id: int,
        images: list[bytes],
        mime_type: str = "image/jpeg"
    ) -> dict[str, Any]:
        """
        Process a batch of receipt photos concurrently:
        - Concurrently parses all receipt photos via AIService.
        - Resolves items and categories for each receipt.
        - Persists all transactions atomically in a single DB commit.
        - Returns a structured summary of processed receipts and total stats.
        """
        if not images:
            raise TransactionParseError("No images provided")

        user = await self.session.get(User, user_id)
        family_group_id = user.family_group_id if user else None

        available_cats = await self.category_service.get_categories(user_id)
        cat_names = list({c.name for c in available_cats})

        parse_tasks = [
            self.ai_service.parse_receipt_photo(img, mime_type, cat_names)
            for img in images
        ]
        raw_payloads = await asyncio.gather(*parse_tasks, return_exceptions=True)

        resolver = BatchCategoryResolver(self, user_id)
        receipts_summary: list[dict[str, Any]] = []
        all_transactions: list[Transaction] = []
        off_topic_count = 0
        error_count = 0

        for idx, payload in enumerate(raw_payloads, start=1):
            if isinstance(payload, Exception):
                logger.warning("Error parsing receipt photo #%d: %s", idx, payload)
                error_count += 1
                continue

            if not isinstance(payload, dict):
                error_count += 1
                continue

            if payload.get("is_financial") is False:
                off_topic_count += 1
                continue

            txs, receipt_title = await self._build_transactions_from_receipt_payload(
                payload=payload,
                user_id=user_id,
                family_group_id=family_group_id,
                resolver=resolver,
                fallback_index=len(receipts_summary) + 1
            )
            if not txs:
                error_count += 1
                continue

            receipt_total = sum(Decimal(str(tx.amount)) for tx in txs)
            receipts_summary.append({
                "receipt_index": len(receipts_summary) + 1,
                "title": receipt_title,
                "total_amount": float(receipt_total),
                "items_count": len(txs),
                "transactions": txs
            })
            all_transactions.extend(txs)

        if not all_transactions:
            if off_topic_count > 0 and off_topic_count == len(images):
                raise OffTopicMessageError("На фотографиях не обнаружены кассовые чеки", raw_text=None)
            raise TransactionParseError("Could not parse receipt photos")

        await self.session.commit()

        total_amount = sum(Decimal(str(tx.amount)) for tx in all_transactions)
        return {
            "receipts": receipts_summary,
            "all_transactions": all_transactions,
            "total_amount": float(total_amount),
            "total_operations": len(all_transactions),
            "processed_count": len(receipts_summary),
            "failed_count": error_count + off_topic_count,
        }

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
            .where(
                Transaction.user_id == user_id,
                Transaction.type == CategoryType.income,
                Transaction.related_transaction_id.is_(None),
            )
        ) or 0

        # Direct liquid income (excluding interest directly capitalized into deposits)
        liquid_income_sum = await self.session.scalar(
            select(func.coalesce(func.sum(Transaction.amount), 0))
            .where(
                Transaction.user_id == user_id,
                Transaction.type == CategoryType.income,
                Transaction.asset_account_id.is_(None)
            )
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
                Transaction.related_transaction_id.is_(None),
                Transaction.transaction_date >= start_month,
                Transaction.transaction_date < next_month,
            )
        ) or 0

        current_balance = (
            initial
            + Decimal(str(liquid_income_sum))
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

    async def update_transaction(
        self,
        user_id: int,
        tx_id: uuid.UUID,
        data: TransactionUpdate,
    ) -> Transaction:
        """
        Atomically updates a transaction (amount, category, item_name) with ownership validation,
        category type verification, asset/credit ledger synchronization, and mirror transaction sync.
        """
        query = (
            select(Transaction)
            .options(joinedload(Transaction.category))
            .where(Transaction.id == tx_id)
        )
        tx = await self.session.scalar(query)
        if not tx:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Транзакция не найдена"
            )

        if tx.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Вы можете редактировать только собственные транзакции"
            )

        # 1. Update category
        if data.category_id is not None and data.category_id != tx.category_id:
            if tx.asset_account_id or tx.credit_account_id or tx.related_transaction_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Изменение категории для переводов, вкладов и кредитов недоступно. Допускается только изменение суммы."
                )

            cat = await self.session.get(Category, data.category_id)
            if not cat:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Указанная категория не найдена"
                )

            if not cat.is_system and cat.user_id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Вы не можете выбрать категорию другого пользователя"
                )

            if cat.type != tx.type:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Тип категории ({cat.type.value}) не соответствует типу операции ({tx.type.value})"
                )

            tx.category_id = cat.id
            tx.category = cat

        # 2. Update item name
        if data.item_name is not None:
            tx.item_name = data.item_name.strip()

        # 3. Update amount and reconcile ledgers
        if data.amount is not None:
            old_amount = Decimal(str(tx.amount))
            new_amount = Decimal(str(data.amount))
            delta = new_amount - old_amount

            if delta != Decimal("0"):
                # Asset / Deposit adjustment
                if tx.asset_account_id:
                    asset = await self.session.get(AssetAccount, tx.asset_account_id)
                    if asset:
                        old_asset_amt = Decimal(str(tx.asset_amount if tx.asset_amount is not None else old_amount))
                        if tx.exchange_rate:
                            new_asset_amt = new_amount * Decimal(str(tx.exchange_rate))
                        else:
                            new_asset_amt = new_amount
                        asset_delta = new_asset_amt - old_asset_amt

                        curr_asset_bal = Decimal(str(asset.balance or 0))
                        if tx.type in (CategoryType.transfer_out, CategoryType.income):
                            asset.balance = float(curr_asset_bal + asset_delta)
                        elif tx.type == CategoryType.transfer_in:
                            asset.balance = float(curr_asset_bal - asset_delta)

                        tx.asset_amount = float(new_asset_amt)

                # Credit adjustment
                if tx.credit_account_id:
                    credit = await self.session.get(CreditAccount, tx.credit_account_id)
                    if credit:
                        curr_rem = Decimal(str(credit.remaining_amount or 0))
                        if tx.type == CategoryType.expense:
                            new_remaining = curr_rem - delta
                            if new_remaining < Decimal("0"):
                                raise HTTPException(
                                    status_code=status.HTTP_400_BAD_REQUEST,
                                    detail="Сумма платежа не может превышать текущий остаток задолженности"
                                )
                            credit.remaining_amount = new_remaining
                            credit.is_active = (new_remaining > Decimal("0"))
                            if new_remaining <= Decimal("0") and not credit.closed_at:
                                credit.closed_at = func.now()
                            elif new_remaining > Decimal("0") and credit.closed_at:
                                credit.closed_at = None
                        elif tx.type == CategoryType.income:
                            credit.original_amount = Decimal(str(credit.original_amount or 0)) + delta
                            credit.remaining_amount = curr_rem + delta

                # Intra-family mirror sync
                if tx.related_transaction_id:
                    mirror_query = select(Transaction).where(Transaction.id == tx.related_transaction_id)
                    mirror_tx = await self.session.scalar(mirror_query)
                    if mirror_tx:
                        mirror_tx.amount = float(new_amount)

                tx.amount = float(new_amount)
                tx.discount_amount = None
                tx.original_amount = None

        await self.session.commit()
        await self.session.refresh(tx)
        return tx

    async def delete_transaction(
        self,
        user_id: int,
        tx_id: uuid.UUID,
    ) -> None:
        """
        Atomically deletes a transaction and reconciles all dependent ledgers:
        1. Validates strict user ownership (tx.user_id == user_id).
        2. Reconciles AssetAccount balance (transfer_out / transfer_in / capitalized interest).
        3. Reconciles CreditAccount debt balance & restores active status (expense repayments).
        4. Safely breaks circular references and cascade-deletes intra-family mirror transactions.
        5. Deletes the primary transaction record within an ACID transaction boundary.
        """
        query = (
            select(Transaction)
            .where(Transaction.id == tx_id)
            .with_for_update()
        )
        tx = await self.session.scalar(query)
        if not tx:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Транзакция не найдена"
            )

        if tx.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Вы можете удалять только собственные транзакции"
            )

        # 1. Ledger Reconciliation: Asset Account
        if tx.asset_account_id:
            asset = await self.session.get(
                AssetAccount,
                tx.asset_account_id,
                with_for_update=True
            )
            if asset:
                delta = Decimal(str(tx.asset_amount if tx.asset_amount is not None else tx.amount))
                curr_asset_bal = Decimal(str(asset.balance or 0))

                if tx.type == CategoryType.transfer_out:
                    # Пополнение депозита отменяется -> баланс вклада уменьшается
                    asset.balance = float(curr_asset_bal - delta)
                elif tx.type == CategoryType.transfer_in:
                    # Снятие с депозита отменяется -> баланс вклада восстанавливается
                    asset.balance = float(curr_asset_bal + delta)
                elif tx.type == CategoryType.income:
                    # Начисленные проценты отменяются -> баланс вклада уменьшается
                    asset.balance = float(curr_asset_bal - Decimal(str(tx.amount)))

        # 2. Ledger Reconciliation: Credit Account
        if tx.credit_account_id:
            credit = await self.session.get(
                CreditAccount,
                tx.credit_account_id,
                with_for_update=True
            )
            if credit:
                if tx.type == CategoryType.expense:
                    # Откат платежа по кредиту: долг увеличивается, кредит возобновляется
                    payment_amt = Decimal(str(tx.amount))
                    curr_rem = Decimal(str(credit.remaining_amount or 0))
                    orig_amount = Decimal(str(credit.original_amount or 0))
                    if orig_amount > Decimal("0.0"):
                        new_remaining = min(orig_amount, curr_rem + payment_amt)
                    else:
                        new_remaining = curr_rem + payment_amt
                    credit.remaining_amount = new_remaining

                    if new_remaining > Decimal("0.0"):
                        credit.is_active = True
                        credit.closed_at = None

                elif tx.type == CategoryType.income:
                    # Откат взятия кредита: проверяем отсутствие платежей
                    repayments_count = await self.session.scalar(
                        select(func.count(Transaction.id)).where(
                            Transaction.credit_account_id == tx.credit_account_id,
                            Transaction.id != tx.id
                        )
                    )
                    if repayments_count and repayments_count > 0:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Невозможно удалить операцию получения кредита, по которому уже зафиксированы платежи погашения"
                        )
                    await self.session.delete(credit)

        # 3. Intra-Family Mirror Transaction Rollback
        if tx.related_transaction_id:
            mirror_query = (
                select(Transaction)
                .where(Transaction.id == tx.related_transaction_id)
                .with_for_update()
            )
            mirror_tx = await self.session.scalar(mirror_query)
            if mirror_tx:
                # Разрываем взаимные ссылки во избежание CircularDependencyError в SQLAlchemy
                tx.related_transaction_id = None
                mirror_tx.related_transaction_id = None
                await self.session.flush()
                await self.session.delete(mirror_tx)

        # 4. Clean deletion of primary transaction
        await self.session.delete(tx)
        await self.session.commit()

    @staticmethod
    def mask_transaction_for_viewer(tx: Transaction, viewer_user_id: int) -> dict[str, Any]:
        """
        Applies unified privacy masking: hides customized deposit/asset names
        and raw prompts from other family members across all API responses.
        """
        is_owner = (tx.user_id == viewer_user_id)
        cat_name = tx.category.name if tx.category else None
        item_name = tx.item_name or cat_name or "Операция"
        raw_text = tx.raw_text if is_owner else None

        if not is_owner:
            is_deposit_op = (
                tx.asset_account_id is not None
                or (cat_name and any(k in cat_name.lower() for k in ["депозит", "вклад", "копилк", "накоплен"]))
                or any(k in item_name.lower() for k in ["депозит", "вклад", "копилк", "накоплен", "процент"])
            )
            if is_deposit_op:
                if "процент" in item_name.lower() or (cat_name and "процент" in cat_name.lower()):
                    item_name = "Проценты по вкладу"
                    cat_name = "Проценты по вкладу"
                elif tx.type in (CategoryType.transfer_out, CategoryType.expense):
                    item_name = "Пополнение депозита"
                    cat_name = "Депозит и вклады"
                else:
                    item_name = "Снятие с депозита"
                    cat_name = "Снятие с депозита"

        return {
            "id": tx.id,
            "user_id": tx.user_id,
            "family_group_id": tx.family_group_id,
            "category_id": tx.category_id,
            "category_name": cat_name,
            "amount": Decimal(str(tx.amount)),
            "original_amount": Decimal(str(tx.original_amount)) if tx.original_amount is not None else None,
            "discount_amount": Decimal(str(tx.discount_amount)) if tx.discount_amount is not None else None,
            "type": tx.type.value if hasattr(tx.type, "value") else str(tx.type),
            "item_name": item_name,
            "raw_text": raw_text,
            "source": tx.source.value if hasattr(tx.source, "value") else str(tx.source),
            "transaction_date": tx.transaction_date,
        }

    async def create_manual_transaction(
        self,
        user: User,
        data: TransactionCreate
    ) -> dict[str, Any]:
        """
        Safely creates a manual transaction via API with complete business validations.
        """
        # 1. Initial balance / onboarding guard
        if user.initial_balance is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Пожалуйста, сначала укажите начальный баланс."
            )

        # 2. Category existence and ownership check
        cat_query = select(Category).where(Category.id == data.category_id)
        category = await self.session.scalar(cat_query)
        if not category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Указанная категория не найдена"
            )
        if not category.is_system and category.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Вы не можете использовать категорию другого пользователя"
            )

        # 3. Category type compatibility
        tx_type = CategoryType(data.type)
        if category.type != tx_type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Тип категории ({category.type.value}) не соответствует типу операции ({tx_type.value})"
            )

        # 4. Construct and persist transaction
        tx = Transaction(
            user_id=user.id,
            family_group_id=user.family_group_id,
            category_id=category.id,
            amount=float(data.amount),
            type=tx_type,
            item_name=data.item_name.strip() if data.item_name else category.name,
            raw_text=data.raw_text,
            source=TransactionSource.manual,
            transaction_date=data.transaction_date or datetime.now(timezone.utc)
        )
        self.session.add(tx)
        await self.session.flush()
        await self.session.refresh(tx)
        tx.category = category
        await self.session.commit()

        return self.mask_transaction_for_viewer(tx, user.id)


