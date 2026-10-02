from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.models.user import User
from src.models.family import FamilyGroup
from src.services.family_service import FamilyService
from src.core.config import settings

router = Router()

def get_miniapp_family_url() -> str:
    domain = settings.domain
    if not domain or domain == "localhost":
        domain = "85.198.89.188.sslip.io:8443"
    elif ":" not in domain and "sslip.io" in domain:
        domain = f"{domain}:8443"
    return f"https://{domain}/app?page=family"

@router.message(Command("family"))
async def cmd_family(message: Message, session: AsyncSession):
    user = await session.get(User, message.from_user.id)
    family_url = get_miniapp_family_url()
    fam_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👨‍👩‍👧‍👦 Открыть Семейный бюджет", web_app=WebAppInfo(url=family_url))]
    ])

    if not user or not user.family_group_id:
        await message.reply(
            "👨‍👩‍👧‍👦 <b>Семейный бюджет Smart Bujet</b>\n\n"
            "Объедините финансовый учет со второй половинкой. Вы будете видеть общие расходы, доходы и совместный баланс в реальном времени.\n\n"
            "Нажмите кнопку ниже, чтобы получить ссылку для приглашения партнера:",
            reply_markup=fam_kb
        )
        return

    group = await session.get(FamilyGroup, user.family_group_id)
    service = FamilyService(session)
    summary = await service.get_family_summary(user)
    members_count = summary.get("member_count", 1)

    if members_count < 2:
        invite_link = summary.get("invite_link")
        await message.reply(
            f"👨‍👩‍👧‍👦 <b>Семейная группа: {group.name}</b>\n\n"
            f"Ожидание подключения партнера.\n"
            f"Ссылка для приглашения:\n<code>{invite_link}</code>\n\n"
            f"Или откройте раздел семьи во весь экран:",
            reply_markup=fam_kb
        )
    else:
        member_names = ", ".join([m["first_name"] for m in summary.get("members", [])])
        await message.reply(
            f"👨‍👩‍👧‍👦 <b>Семейная группа: {group.name}</b>\n"
            f"👥 Участники: {member_names}\n"
            f"💰 Совместный баланс: <b>{summary['combined_balance']} {summary['currency']}</b>\n\n"
            f"Управляйте совместным бюджетом во весь экран:",
            reply_markup=fam_kb
        )

@router.message(Command("family_leave"))
async def cmd_family_leave(message: Message, session: AsyncSession):
    user = await session.get(User, message.from_user.id)
    if not user:
        return
    service = FamilyService(session)
    success, partner_id = await service.leave_group(user)
    if success:
        if partner_id:
            try:
                author_title = user.first_name or f"@{user.username}" or "Партнёр"
                await message.bot.send_message(
                    partner_id,
                    f"ℹ️ <b>{author_title}</b> покинул(а) семейную группу.\n"
                    f"Семейный бюджет больше не синхронизируется."
                )
            except Exception:
                pass
        await message.reply("👋 Вы вышли из семейной группы.")
    else:
        await message.reply("Вы не состоите ни в одной семейной группе.")
