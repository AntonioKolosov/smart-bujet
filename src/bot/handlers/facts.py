import html
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.user import User
from src.models.agent_memory import UserAgentMemory, FactCategory
from src.bot.keyboards.inline import get_miniapp_url

router = Router()

CATEGORY_ICONS = {
    FactCategory.goal.value: "🎯 Цель",
    FactCategory.habit.value: "🔄 Привычка",
    FactCategory.schedule.value: "📅 Расписание",
    FactCategory.constraint.value: "⛔ Ограничение",
    FactCategory.other.value: "💡 Заметка",
}


@router.message(Command("facts"))
@router.message(Command("profile"))
async def cmd_facts(message: Message, session: AsyncSession):
    user_id = message.from_user.id
    user = await session.get(User, user_id)
    if not user:
        await message.answer("⚠️ Вы ещё не зарегистрированы. Отправьте команду /start")
        return

    memories = (await session.scalars(
        select(UserAgentMemory)
        .where(UserAgentMemory.user_id == user_id, UserAgentMemory.is_active == True)
        .order_by(UserAgentMemory.created_at.desc())
    )).all()

    lines = ["🧠 <b>Персонализация и контекст агента</b>\n"]
    if not memories:
        lines.append(
            "<i>У вас пока нет сохранённых фактов о целях, привычках или расписании.</i>\n\n"
            "Добавьте их в приложении, чтобы Smart Bujet давал персонализированные финансовые советы!"
        )
    else:
        lines.append("Сохранённые факты о вас:")
        for idx, m in enumerate(memories, 1):
            cat_label = CATEGORY_ICONS.get(m.category, "💡 Заметка")
            lines.append(f"{idx}. [{cat_label}] {html.escape(m.fact_text)}")
        lines.append("\nВы можете управлять фактами в приложении:")

    base_url = get_miniapp_url()
    sep = "&" if "?" in base_url else "?"
    app_url = f"{base_url}{sep}page=facts"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧠 Открыть Персонализацию", web_app=WebAppInfo(url=app_url))]
    ])
    await message.answer("\n".join(lines), reply_markup=kb)
