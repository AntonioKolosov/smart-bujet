import uuid
import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.transaction import Transaction
from src.models.category import Category, CategoryType
from src.models.user import User
from src.models.alias import UserItemAlias
from src.models.dynamic_context import UserClassificationFeedback
from src.services.transaction_service import TransactionService
from src.services.category_service import CategoryService
from src.bot.messages import BotMessages, format_amount
from src.bot.keyboards.inline import tx_toggle_keyboard

router = Router()
logger = logging.getLogger(__name__)


@router.callback_query(F.data.startswith("tx_toggle:"))
async def handle_tx_toggle(callback: CallbackQuery, session: AsyncSession):
    raw_id = callback.data.split(":", 1)[1]
    try:
        tx_id = uuid.UUID(raw_id)
    except ValueError:
        await callback.answer("❌ Некорректный ID транзакции", show_alert=True)
        return

    tx = await session.get(Transaction, tx_id)
    if not tx:
        await callback.answer("❌ Транзакция не найдена", show_alert=True)
        return

    if tx.user_id != callback.from_user.id:
        await callback.answer("⛔ Вы можете изменять только свои транзакции", show_alert=True)
        return

    old_type = tx.type
    if old_type == CategoryType.expense:
        new_type = CategoryType.income
        toast_msg = "✅ Изменено на Доход"
    elif old_type == CategoryType.income:
        new_type = CategoryType.expense
        toast_msg = "✅ Изменено на Расход"
    else:
        await callback.answer("⚠️ Операции со счетами и активами изменяются в меню Депозитов", show_alert=True)
        return

    cat_service = CategoryService(session)
    old_cat_id = tx.category_id
    old_cat_name = tx.category.name if tx.category else "Общее"

    # Resolve matching category for the opposite type
    new_cat = await cat_service.find_by_name(old_cat_name, cat_type=new_type, user_id=tx.user_id)
    if not new_cat:
        # Fallback to «Денежный перевод» or first available category of new type
        fallback_name = "Денежный перевод" if any(w in (tx.item_name or "").lower() for w in ["перевод", "долг", "друг"]) else None
        if fallback_name:
            new_cat = await cat_service.find_by_name(fallback_name, cat_type=new_type, user_id=tx.user_id)
        if not new_cat:
            cats = await cat_service.get_categories(user_id=tx.user_id, cat_type=new_type)
            new_cat = cats[0] if cats else None

    if not new_cat:
        await callback.answer("❌ Не найдена подходящая категория", show_alert=True)
        return

    # Update transaction
    tx.type = new_type
    tx.category_id = new_cat.id
    tx.category = new_cat

    # If this had a mirror transaction, disconnect it upon manual flip
    if tx.related_transaction_id:
        mirror_tx = await session.get(Transaction, tx.related_transaction_id)
        if mirror_tx:
            mirror_tx.related_transaction_id = None
        tx.related_transaction_id = None

    # Real-time alias healing: rewrite alias so future inputs automatically use corrected category
    if tx.item_name:
        norm_name = tx.item_name.strip().lower()
        alias_query = select(UserItemAlias).where(
            UserItemAlias.user_id == tx.user_id,
            UserItemAlias.item_name_normalized == norm_name
        )
        alias = await session.scalar(alias_query)
        if alias:
            alias.category_id = new_cat.id
            alias.usage_count += 1
        else:
            session.add(UserItemAlias(
                user_id=tx.user_id,
                item_name_normalized=norm_name,
                category_id=new_cat.id,
                usage_count=1
            ))

    # Active learning log
    feedback = UserClassificationFeedback(
        user_id=tx.user_id,
        transaction_id=tx.id,
        original_text=tx.raw_text or tx.item_name,
        original_type=old_type.value,
        corrected_type=new_type.value,
        original_category_id=old_cat_id,
        corrected_category_id=new_cat.id
    )
    session.add(feedback)

    # Recalculate balance and commit
    tx_service = TransactionService(session)
    bal_data = await tx_service.get_user_balance(tx.user_id)
    await session.commit()

    # Edit message with updated text and dynamically swapped button
    user = await session.get(User, tx.user_id)
    currency = user.currency if user else "KZT"
    new_text = BotMessages.tx_success(
        transactions=tx,
        currency=currency,
        current_balance=bal_data["current_balance"]
    )
    new_keyboard = tx_toggle_keyboard(tx)

    try:
        await callback.message.edit_text(
            text=new_text,
            reply_markup=new_keyboard
        )
    except Exception as exc:
        logger.warning("Could not edit message text on toggle: %s", exc)

    amt_formatted = format_amount(tx.amount, currency)
    await callback.answer(f"{toast_msg} ({amt_formatted})")
