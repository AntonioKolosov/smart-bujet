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
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.user import User
from src.services.report_service import ReportService
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


def summary_inline_keyboard(
    active_period: str,
    active_scope: str,
    has_family: bool
) -> InlineKeyboardMarkup:
    """Interactive inline keyboard for period switching and personal/family toggle."""
    periods = [("week", "7 дней"), ("month", "Месяц"), ("year", "Год")]
    period_btns = []
    for code, label in periods:
        text = f"• {label} •" if code == active_period else label
        period_btns.append(InlineKeyboardButton(text=text, callback_data=f"sum:{code}:{active_scope}"))

    rows = [period_btns]
    if has_family:
        p_text = "• 👤 Личная •" if active_scope == "p" else "👤 Личная"
        f_text = "• 👨‍👩‍👧‍👦 Семья •" if active_scope == "f" else "👨‍👩‍👧‍👦 Семья"
        rows.append([
            InlineKeyboardButton(text=p_text, callback_data=f"sum:{active_period}:p"),
            InlineKeyboardButton(text=f_text, callback_data=f"sum:{active_period}:f"),
        ])

    rows.append([
        InlineKeyboardButton(text="🔄 Обновить", callback_data=f"sum:{active_period}:{active_scope}")
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(Command("summary"))
@router.message(Command("report"))
@router.message(F.text.in_(["📊 Сводка", "Сводка", "сводка", "Отчет", "отчет", "📊 Отчет"]))
async def cmd_summary(message: Message, session: AsyncSession):
    user = await session.get(User, message.from_user.id)
    if not user:
        return

    report_service = ReportService(session)
    ai_service = AIService()

    # Default view: current month, personal scope
    summary = await report_service.get_agent_analytics(user_id=user.id, period="month")
    advice = await ai_service.generate_financial_advice(summary)

    text = format_summary_card(summary, advice)
    kb = summary_inline_keyboard(
        active_period="month",
        active_scope="p",
        has_family=bool(user.family_group_id)
    )
    await message.answer(text, reply_markup=kb)


@router.callback_query(F.data.startswith("sum:"))
async def on_summary_switch(callback: CallbackQuery, session: AsyncSession):
    parts = callback.data.split(":")
    if len(parts) < 3:
        await callback.answer()
        return

    period = parts[1]
    scope = parts[2]
    user_id = callback.from_user.id

    user = await session.get(User, user_id)
    if not user:
        await callback.answer()
        return

    fam_id = user.family_group_id if scope == "f" else None
    report_service = ReportService(session)
    ai_service = AIService()

    summary = await report_service.get_agent_analytics(
        user_id=user.id,
        family_group_id=fam_id,
        period=period
    )
    advice = await ai_service.generate_financial_advice(summary)

    text = format_summary_card(summary, advice)
    kb = summary_inline_keyboard(
        active_period=period,
        active_scope=scope,
        has_family=bool(user.family_group_id)
    )

    try:
        await callback.message.edit_text(text, reply_markup=kb)
    except Exception as exc:
        logger.debug("Could not edit summary message: %s", exc)

    await callback.answer()
