from __future__ import annotations

import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.user import User
from src.services.report_service import ReportService
from src.services.family_service import FamilyService
from src.services.ai_service import AIService
from src.bot.messages import format_summary_card

logger = logging.getLogger(__name__)

router = Router()


def summary_reply_keyboard() -> ReplyKeyboardMarkup:
    """Persistent reply keyboard button for quick summary invocation."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📊 Сводка")]],
        resize_keyboard=True,
        is_persistent=True,
    )


def summary_scope_selection_keyboard() -> InlineKeyboardMarkup:
    """Initial inline keyboard asking user to choose personal or family summary."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="👤 Личный", callback_data="sum:scope:p"),
                InlineKeyboardButton(text="👨‍👩‍👧‍👦 Семья", callback_data="sum:scope:f"),
            ]
        ]
    )


def summary_card_inline_keyboard(active_scope: str) -> InlineKeyboardMarkup:
    """
    Compact inline keyboard for current moment summary.
    Eliminates period switcher buttons ('7 дней', 'Месяц', 'Год').
    Allows instant refresh and one-tap toggle between personal and family views.
    """
    if active_scope == "p":
        row = [
            InlineKeyboardButton(text="🔄 Обновить", callback_data="sum:refresh:p"),
            InlineKeyboardButton(text="👨‍👩‍👧‍👦 Семья", callback_data="sum:scope:f"),
        ]
    else:
        row = [
            InlineKeyboardButton(text="🔄 Обновить", callback_data="sum:refresh:f"),
            InlineKeyboardButton(text="👤 Личный", callback_data="sum:scope:p"),
        ]
    return InlineKeyboardMarkup(inline_keyboard=[row])


def summary_no_family_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for users requesting family summary without an active partner."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👤 Личный", callback_data="sum:scope:p")]
        ]
    )


def broadcast_digest_keyboard() -> InlineKeyboardMarkup:
    """Fixed digest keyboard for scheduled broadcasts without period switcher buttons."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📊 Сводка на текущий момент", callback_data="sum:scope:p")]
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
@router.message(F.text.in_(["📊 Сводка", "Сводка", "сводка"]))
async def cmd_summary(message: Message, session: AsyncSession):
    """
    Step 1 of refined UX flow:
    Lightweight prompt asking user to choose between personal or family summary.
    Zero LLM calls, zero DB overhead, instant response.
    """
    user = await session.get(User, message.from_user.id)
    if not user:
        return

    text = "📊 <b>Финансовая сводка</b>\n\nВыберите какую сводку сформировать на текущий момент:"
    kb = summary_scope_selection_keyboard()
    await message.answer(text, reply_markup=kb)


@router.callback_query(F.data.startswith("sum:"))
async def on_summary_callback(callback: CallbackQuery, session: AsyncSession):
    """
    Step 2 of refined UX flow:
    Handles scope selection ('sum:scope:p', 'sum:scope:f'), refresh ('sum:refresh:p', 'sum:refresh:f'),
    and backwards-compatible legacy callbacks.
    """
    parts = callback.data.split(":")
    if len(parts) < 3:
        await callback.answer()
        return

    action = parts[1]
    scope = parts[2]
    user_id = callback.from_user.id

    # Normalize scope for legacy callbacks (e.g. sum:month:p)
    if scope not in ("p", "f"):
        scope = "p"

    user = await session.get(User, user_id)
    if not user:
        await callback.answer()
        return

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
            fam_service = FamilyService(session)
            group = await fam_service.get_or_create_user_family(user)
            invite_link = fam_service.build_invite_link(group.invite_code)

            text = (
                "👨‍👩‍👧‍👦 <b>Семейная сводка пока недоступна</b>\n\n"
                "У вас ещё не подключен партнер. Объедините бюджет со второй половинкой, чтобы видеть "
                "общие расходы, доходы и семейную подушку безопасности в реальном времени.\n\n"
                f"🔗 <b>Ссылка для подключения партнера:</b>\n<code>{invite_link}</code>\n\n"
                "<i>Отправьте эту ссылку партнеру в Telegram. После того как партнер перейдет по ней, "
                "ваш семейный бюджет синхронизируется.</i>"
            )
            kb = summary_no_family_keyboard()
            try:
                await callback.message.edit_text(text, reply_markup=kb)
            except Exception as exc:
                logger.debug("Could not edit message for family invite: %s", exc)
            await callback.answer()
            return

        summary = await report_service.get_agent_analytics(
            user_id=user.id,
            family_group_id=user.family_group_id,
            period="month"
        )
        advice = await ai_service.generate_financial_advice(summary)
        text = format_summary_card(summary, advice)
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
    text = format_summary_card(summary, advice)
    kb = summary_card_inline_keyboard(active_scope="p")

    try:
        await callback.message.edit_text(text, reply_markup=kb)
    except Exception as exc:
        logger.debug("Could not edit summary message: %s", exc)

    if action == "refresh":
        await callback.answer("Сводка обновлена")
    else:
        await callback.answer()
