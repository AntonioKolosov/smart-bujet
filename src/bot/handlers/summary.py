from __future__ import annotations

import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardRemove,
)
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.user import User
from src.services.report_service import ReportService
from src.services.ai_service import AIService
from src.services.transaction_service import TransactionService
from src.bot.messages import BotMessages, format_summary_card
from src.bot.keyboards.inline import welcome_back_keyboard, get_miniapp_url

logger = logging.getLogger(__name__)

router = Router()


def summary_scope_selection_keyboard() -> InlineKeyboardMarkup:
    """Inline keyboard asking user to choose personal or family summary, or go back to main menu."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="👤 Личная", callback_data="sum:scope:p"),
                InlineKeyboardButton(text="👨‍👩‍👧‍👦 Семейная", callback_data="sum:scope:f"),
            ],
            [
                InlineKeyboardButton(text="🔙 Назад", callback_data="sum:back:main"),
            ]
        ]
    )


def summary_card_inline_keyboard(active_scope: str) -> InlineKeyboardMarkup:
    """
    Compact inline keyboard for current moment summary card.
    Eliminates refresh button. Provides one-tap toggle between personal and family views,
    and direct button to return to the main menu.
    """
    if active_scope == "p":
        row1 = [
            InlineKeyboardButton(text="👨‍👩‍👧‍👦 Семейная", callback_data="sum:scope:f"),
        ]
    else:
        row1 = [
            InlineKeyboardButton(text="👤 Личная", callback_data="sum:scope:p"),
        ]
    row2 = [
        InlineKeyboardButton(text="📋 В меню", callback_data="sum:back:main"),
    ]
    return InlineKeyboardMarkup(inline_keyboard=[row1, row2])


def summary_no_family_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for users requesting family summary without an active partner."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👤 Личная", callback_data="sum:scope:p")],
            [InlineKeyboardButton(text="📋 В меню", callback_data="sum:back:main")],
        ]
    )


def broadcast_digest_keyboard() -> InlineKeyboardMarkup:
    """Fixed digest keyboard for scheduled broadcasts without period switcher buttons."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📊 Сводка от агента", callback_data="sum:menu")]
        ]
    )


def summary_inline_keyboard(
    active_period: str = "month",
    active_scope: str = "p",
    has_family: bool = False
) -> InlineKeyboardMarkup:
    """Backwards-compatible helper returning clean broadcast digest keyboard."""
    return broadcast_digest_keyboard()


@router.message(Command("summary"))
@router.message(F.text.in_(["📊 Сводка", "Сводка", "сводка", "Сводка от агента", "📊 Сводка от агента"]))
async def cmd_summary(message: Message, session: AsyncSession):
    """
    Step 1 of refined UX flow:
    Lightweight prompt asking user to choose between personal or family summary.
    Zero LLM calls, zero DB overhead, instant response.
    """
    user = await session.get(User, message.from_user.id)
    if not user:
        return

    # Strip lingering persistent reply keyboard if present in Telegram client
    try:
        clean_msg = await message.answer("🔄", reply_markup=ReplyKeyboardRemove())
        await clean_msg.delete()
    except Exception:
        pass

    text = "📊 <b>Финансовая сводка от агента</b>\n\nВыберите какую сводку сформировать:"
    kb = summary_scope_selection_keyboard()
    await message.answer(text, reply_markup=kb)


@router.callback_query(F.data.startswith("sum:"))
async def on_summary_callback(callback: CallbackQuery, session: AsyncSession):
    """
    Step 2 of refined UX flow:
    Handles scope prompt ('sum:menu'), back to main menu ('sum:back:main'),
    scope selection ('sum:scope:p', 'sum:scope:f'), refresh ('sum:refresh:p', 'sum:refresh:f'),
    and backwards-compatible legacy callbacks.
    """
    data = callback.data or ""
    user_id = callback.from_user.id

    user = await session.get(User, user_id)
    if not user:
        await callback.answer()
        return

    # 1. Back to Main Welcome Menu
    if data == "sum:back:main":
        tx_service = TransactionService(session)
        bal_data = await tx_service.get_user_balance(user.id)
        miniapp_url = get_miniapp_url()
        text = BotMessages.welcome_back(
            first_name=user.first_name,
            currency=user.currency,
            current_balance=bal_data["current_balance"]
        )
        kb = welcome_back_keyboard(miniapp_url=miniapp_url)
        try:
            await callback.message.edit_text(text, reply_markup=kb)
        except Exception as exc:
            logger.debug("Could not edit message back to main menu: %s", exc)
        await callback.answer()
        return

    # 2. Scope Selection Prompt (from "📊 Сводка от агента" button or "🔙 Назад" from summary card)
    if data in ("sum:menu", "sum:choose"):
        text = "📊 <b>Финансовая сводка от агента</b>\n\nВыберите какую сводку сформировать:"
        kb = summary_scope_selection_keyboard()
        try:
            await callback.message.edit_text(text, reply_markup=kb)
        except Exception as exc:
            logger.debug("Could not edit message to summary scope prompt: %s", exc)
        await callback.answer()
        return

    parts = data.split(":")
    if len(parts) < 3:
        await callback.answer()
        return

    action = parts[1]
    scope = parts[2]

    # Normalize scope for legacy callbacks (e.g. sum:month:p)
    if scope not in ("p", "f"):
        scope = "p"

    report_service = ReportService(session)
    ai_service = AIService()

    # Scope: Family
    if scope == "f":
        has_partner = False
        if user.family_group_id:
            count_res = await session.scalar(
                select(func.count(User.id)).where(User.family_group_id == user.family_group_id)
            )
            has_partner = (count_res or 0) >= 2

        if not has_partner:
            text = "👨‍👩‍👧‍👦 <b>Вы не состоите в семейной группе</b>"
            kb = summary_no_family_keyboard()
            if callback.message:
                try:
                    await callback.message.edit_text(text, reply_markup=kb)
                except Exception as exc:
                    logger.debug("Could not edit message for family guard: %s", exc)
            await callback.answer(text="Вы не состоите в семейной группе", show_alert=True)
            return

        summary = await report_service.get_agent_analytics(
            user_id=user.id,
            family_group_id=user.family_group_id,
            period="month"
        )
        advice = await ai_service.generate_financial_advice(summary)
        text = format_summary_card(summary, advice, period_label="на текущую дату")
        kb = summary_card_inline_keyboard(active_scope="f")

        try:
            await callback.message.edit_text(text, reply_markup=kb)
        except Exception as exc:
            logger.debug("Could not edit summary message: %s", exc)

        if action == "refresh":
            await callback.answer("Семейная сводка обновлена")
        else:
            await callback.answer()
        return

    # Scope: Personal
    summary = await report_service.get_agent_analytics(
        user_id=user.id,
        family_group_id=None,
        period="month"
    )
    advice = await ai_service.generate_financial_advice(summary)
    text = format_summary_card(summary, advice, period_label="на текущую дату")
    kb = summary_card_inline_keyboard(active_scope="p")

    try:
        await callback.message.edit_text(text, reply_markup=kb)
    except Exception as exc:
        logger.debug("Could not edit summary message: %s", exc)

    if action == "refresh":
        await callback.answer("Личная сводка обновлена")
    else:
        await callback.answer()
