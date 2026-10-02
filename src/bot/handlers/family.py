from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.models.user import User
from src.models.family import FamilyGroup
from src.services.family_service import FamilyService

router = Router()

@router.message(Command("family"))
async def cmd_family(message: Message, session: AsyncSession):
    user = await session.get(User, message.from_user.id)
    if not user or not user.family_group_id:
        await message.reply(
            "👥 Вы пока не состоите в семейной группе.\n\n"
            "Команды:\n"
            "▫️ <code>/family_create Название</code> — создать группу\n"
            "▫️ <code>/family_join КОД</code> — присоединиться по коду"
        )
        return

    group = await session.get(FamilyGroup, user.family_group_id)
    service = FamilyService(session)
    members = await service.get_group_members(group.id)
    member_names = ", ".join([f"@{m.username}" if m.username else f"ID:{m.id}" for m in members])

    await message.reply(
        f"👨‍👩‍👧‍👦 <b>Семейная группа: {group.name}</b>\n"
        f"🔑 Код приглашения: <code>{group.invite_code}</code>\n"
        f"👥 Участники ({len(members)}): {member_names}\n\n"
        f"Отправьте этот код близким, чтобы они подключились через <code>/family_join {group.invite_code}</code>\n"
        f"Покинуть группу: <code>/family_leave</code>"
    )

@router.message(Command("family_create"))
async def cmd_family_create(message: Message, session: AsyncSession):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply("Укажите название группы. Пример: <code>/family_create Семья Ивановых</code>")
        return

    name = args[1].strip()
    service = FamilyService(session)
    group = await service.create_group(owner_id=message.from_user.id, name=name)

    await message.reply(
        f"🎉 <b>Группа \"{group.name}\" создана!</b>\n"
        f"🔑 Код приглашения: <code>{group.invite_code}</code>\n\n"
        f"Другие участники могут присоединиться командой:\n"
        f"<code>/family_join {group.invite_code}</code>"
    )

@router.message(Command("family_join"))
async def cmd_family_join(message: Message, session: AsyncSession):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply("Укажите код приглашения. Пример: <code>/family_join XYZ123</code>")
        return

    invite_code = args[1].strip()
    service = FamilyService(session)
    group = await service.join_group(user_id=message.from_user.id, invite_code=invite_code)
    if not group:
        await message.reply("❌ Группа с таким кодом приглашения не найдена.")
        return

    await message.reply(f"✅ Вы успешно присоединились к группе <b>\"{group.name}\"</b>!")

@router.message(Command("family_leave"))
async def cmd_family_leave(message: Message, session: AsyncSession):
    service = FamilyService(session)
    success = await service.leave_group(user_id=message.from_user.id)
    if success:
        await message.reply("👋 Вы вышли из семейной группы.")
    else:
        await message.reply("Вы не состоите ни в одной семейной группе.")

