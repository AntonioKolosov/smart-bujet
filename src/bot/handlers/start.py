from aiogram import Router, F
from aiogram.filters import CommandStart, Command, CommandObject
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.models.user import User
from src.core.config import settings
from src.bot.keyboards.inline import (
    currency_keyboard,
    welcome_back_keyboard,
    miniapp_keyboard,
    deposits_keyboard,
    credits_keyboard,
    family_keyboard,
    analytics_keyboard,
    get_miniapp_url,
)
from src.bot.messages import BotMessages
from src.services.transaction_service import TransactionService
from src.services.family_service import FamilyService

router = Router()

def get_miniapp_url() -> str:
    domain = settings.domain
    if not domain or domain == "localhost":
        domain = "85.198.89.188.sslip.io:8443"
    elif ":" not in domain and "sslip.io" in domain:
        domain = f"{domain}:8443"
    return f"https://{domain}/app"

@router.message(Command("miniapp"))
@router.message(Command("app"))
async def cmd_miniapp(message: Message):
    url = get_miniapp_url()
    await message.answer(
        "📱 Нажмите кнопку ниже, чтобы открыть журнал транзакций во весь экран:",
        reply_markup=miniapp_keyboard(url)
    )

@router.message(Command("deposits"))
@router.message(Command("assets"))
async def cmd_deposits(message: Message):
    url = f"{get_miniapp_url()}?page=deposits"
    await message.answer(
        "🏦 <b>Депозиты, сбережения и валютные счета</b>\n\n"
        "Управляйте вашими банковскими вкладами, копилками и валютными счетами во весь экран:",
        reply_markup=deposits_keyboard(url)
    )

@router.message(Command("credits"))
@router.message(Command("loans"))
async def cmd_credits(message: Message):
    url = f"{get_miniapp_url()}?page=credits"
    await message.answer(
        "💳 <b>Кредиты и займы</b>\n\n"
        "Отслеживайте активные кредиты, остаток долга и график погашения во весь экран:",
        reply_markup=credits_keyboard(url)
    )

@router.message(Command("analytics"))
@router.message(Command("stats"))
async def cmd_analytics(message: Message):
    url = f"{get_miniapp_url()}?page=analytics"
    await message.answer(
        "📊 <b>Финансовая аналитика и статистика</b>\n\n"
        "Смотрите круговые диаграммы по категориям трат и помесячную динамику расходов во весь экран:",
        reply_markup=analytics_keyboard(url)
    )

@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession, command: CommandObject):
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    
    user = await session.scalar(select(User).where(User.id == user_id))
    is_new_user = False
    
    if not user:
        user = User(id=user_id, username=None, first_name=first_name, currency="KZT", has_accepted_terms=False)
        session.add(user)
        await session.commit()
        is_new_user = True
    else:
        user.username = None  # Admin blindness: do not persist username
        if user.first_name != first_name:
            user.first_name = first_name
        await session.commit()

    # Check for Family Invite Deep Link: /start fam_<invite_code>
    if command and command.args and command.args.startswith("fam_"):
        invite_code = command.args[4:]
        fam_service = FamilyService(session)
        group, partner_id, feedback_msg = await fam_service.join_by_invite(user, invite_code)

        if group and partner_id:
            try:
                author_title = user.first_name or (f"@{user.username}" if user.username else "Партнёр")
                await message.bot.send_message(
                    partner_id,
                    f"🎉 <b>{author_title}</b> присоединился(лась) к вашей семейной группе <b>«{group.name}»</b>!\n\n"
                    f"Теперь ваши расходы и доходы объединены во вкладке «Семья» в MiniApp."
                )
            except Exception:
                pass

        family_url = f"{get_miniapp_url()}?page=family"
        if user.initial_balance is None:
            await message.answer(
                f"👨‍👩‍👧‍👦 <b>Семейный бюджет</b>\n\n{feedback_msg}\n\n{BotMessages.ask_initial_balance()}",
                reply_markup=family_keyboard(family_url)
            )
        else:
            await message.answer(
                f"👨‍👩‍👧‍👦 <b>Семейный бюджет</b>\n\n{feedback_msg}\n\n"
                f"Нажмите кнопку ниже, чтобы открыть общий семейный бюджет:",
                reply_markup=family_keyboard(family_url)
            )
        return

    if is_new_user or not getattr(user, "has_accepted_terms", True):
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        privacy_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Принимаю условия", callback_data="privacy:accept")]
        ])
        await message.answer(
            f"🛡 <b>Политика конфиденциальности и защита данных</b>\n\n"
            f"Добро пожаловать в <b>Smart Буджет</b>! Перед началом работы ознакомьтесь с правилами безопасности:\n\n"
            f"• 🔒 <b>Сквозное шифрование (AES-256-GCM):</b> названия ваших покупок, счетов и кредитов зашифрованы в базе данных.\n"
            f"• 🛡 <b>Guardrails-маскирование:</b> перед отправкой в AI имена, номера карт и телефоны обезличиваются.\n"
            f"• 🙈 <b>Слепота администратора:</b> ваш @username не сохраняется в базе данных.\n"
            f"• 🗑 <b>Право на удаление:</b> в любой момент команда /delete_account безвозвратно удаляет все ваши данные.\n\n"
            f"Нажимая кнопку ниже, вы соглашаетесь на обработку данных финансовым ассистентом.",
            reply_markup=privacy_kb
        )
        return

    if user.initial_balance is None:
        await message.answer(
            f"👋 <b>С возвращением, {user.first_name or ''}!</b>\n\n{BotMessages.ask_initial_balance()}",
            reply_markup=ReplyKeyboardRemove()
        )
        return

    tx_service = TransactionService(session)
    bal_data = await tx_service.get_user_balance(user.id)
    miniapp_url = get_miniapp_url()

    # Clear any residual persistent reply keyboard
    try:
        clean_msg = await message.answer("🔄", reply_markup=ReplyKeyboardRemove())
        await clean_msg.delete()
    except Exception:
        pass

    await message.answer(
        BotMessages.welcome_back(
            first_name=user.first_name,
            currency=user.currency,
            current_balance=bal_data["current_balance"]
        ),
        reply_markup=welcome_back_keyboard(miniapp_url=miniapp_url)
    )

@router.callback_query(F.data == "change_currency")
async def on_change_currency(callback: CallbackQuery):
    await callback.message.edit_text(
        "Выберите новую валюту:",
        reply_markup=currency_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "privacy:accept")
async def on_privacy_accept(callback: CallbackQuery, session: AsyncSession):
    user = await session.scalar(select(User).where(User.id == callback.from_user.id))
    if user:
        user.has_accepted_terms = True
        await session.commit()

    if not user or user.initial_balance is None:
        await callback.message.edit_text(
            BotMessages.welcome_new(),
            reply_markup=currency_keyboard()
        )
    else:
        miniapp_url = get_miniapp_url()
        await callback.message.edit_text(
            f"✅ Условия конфиденциальности приняты!\n\n{BotMessages.welcome_back(user.first_name, user.currency, 0.0)}",
            reply_markup=welcome_back_keyboard(miniapp_url=miniapp_url)
        )
    await callback.answer()


@router.message(Command("delete_account"))
async def cmd_delete_account(message: Message):
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    confirm_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Да, безвозвратно удалить всё", callback_data="act:delete:confirm")],
        [InlineKeyboardButton(text="🔙 Отмена", callback_data="act:delete:cancel")]
    ])
    await message.answer(
        "⚠️ <b>Внимание! Полное удаление аккаунта</b>\n\n"
        "Вы действительно хотите безвозвратно удалить свой профиль и ВСЮ историю транзакций, счетов и кредитов?\n\n"
        "Это действие невозможно отменить.",
        reply_markup=confirm_kb
    )


@router.callback_query(F.data == "act:delete:cancel")
async def on_delete_cancel(callback: CallbackQuery):
    await callback.message.edit_text("Действие отменено.")
    await callback.answer()


@router.callback_query(F.data == "act:delete:confirm")
async def on_delete_confirm(callback: CallbackQuery, session: AsyncSession):
    user = await session.scalar(select(User).where(User.id == callback.from_user.id))
    if not user:
        await callback.message.edit_text("Аккаунт не найден.")
        await callback.answer()
        return

    from src.models.family import FamilyGroup
    if user.family_group_id:
        family = await session.get(FamilyGroup, user.family_group_id)
        if family and family.owner_id == user.id:
            other_member = await session.scalar(
                select(User).where(User.family_group_id == family.id, User.id != user.id)
            )
            if other_member:
                family.owner_id = other_member.id
                user.family_group_id = None
                await session.flush()
            else:
                user.family_group_id = None
                await session.flush()
                await session.delete(family)
                await session.flush()
        else:
            user.family_group_id = None
            await session.flush()

    await session.delete(user)
    await session.commit()
    await callback.message.edit_text("🗑 <b>Ваш аккаунт и все данные успешно и безвозвратно удалены.</b>\n\nЕсли захотите вернуться, просто отправьте /start.")
    await callback.answer()

@router.callback_query(F.data.startswith("currency_"))
async def process_currency(callback: CallbackQuery, session: AsyncSession):
    currency = callback.data.split("_")[1]
    user_id = callback.from_user.id
    
    user = await session.scalar(select(User).where(User.id == user_id))
    if user:
        user.currency = currency
        await session.commit()

    if user and user.initial_balance is None:
        await callback.message.edit_text(
            f"{BotMessages.currency_updated(currency)}\n\n{BotMessages.ask_initial_balance()}"
        )
    else:
        miniapp_url = get_miniapp_url()
        await callback.message.edit_text(
            BotMessages.currency_updated(currency),
            reply_markup=welcome_back_keyboard(miniapp_url=miniapp_url)
        )
    await callback.answer()


@router.callback_query(F.data == "privacy:accept")
async def on_privacy_accept(callback: CallbackQuery, session: AsyncSession):
    user = await session.scalar(select(User).where(User.id == callback.from_user.id))
    if user:
        user.has_accepted_terms = True
        await session.commit()

    if not user or user.initial_balance is None:
        await callback.message.edit_text(
            BotMessages.welcome_new(),
            reply_markup=currency_keyboard()
        )
    else:
        miniapp_url = get_miniapp_url()
        await callback.message.edit_text(
            f"✅ Условия конфиденциальности приняты!\n\n{BotMessages.welcome_back(user.first_name, user.currency, 0.0)}",
            reply_markup=welcome_back_keyboard(miniapp_url=miniapp_url)
        )
    await callback.answer()


@router.message(Command("delete_account"))
async def cmd_delete_account(message: Message):
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    confirm_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Да, безвозвратно удалить всё", callback_data="act:delete:confirm")],
        [InlineKeyboardButton(text="🔙 Отмена", callback_data="act:delete:cancel")]
    ])
    await message.answer(
        "⚠️ <b>Внимание! Полное удаление аккаунта</b>\n\n"
        "Вы действительно хотите безвозвратно удалить свой профиль и ВСЮ историю транзакций, счетов и кредитов?\n\n"
        "Это действие невозможно отменить.",
        reply_markup=confirm_kb
    )


@router.callback_query(F.data == "act:delete:cancel")
async def on_delete_cancel(callback: CallbackQuery):
    await callback.message.edit_text("Действие отменено.")
    await callback.answer()


@router.callback_query(F.data == "act:delete:confirm")
async def on_delete_confirm(callback: CallbackQuery, session: AsyncSession):
    user = await session.scalar(select(User).where(User.id == callback.from_user.id))
    if not user:
        await callback.message.edit_text("Аккаунт не найден.")
        await callback.answer()
        return

    from src.models.family import FamilyGroup
    if user.family_group_id:
        family = await session.get(FamilyGroup, user.family_group_id)
        if family and family.owner_id == user.id:
            other_member = await session.scalar(
                select(User).where(User.family_group_id == family.id, User.id != user.id)
            )
            if other_member:
                family.owner_id = other_member.id
                user.family_group_id = None
                await session.flush()
            else:
                user.family_group_id = None
                await session.flush()
                await session.delete(family)
                await session.flush()
        else:
            user.family_group_id = None
            await session.flush()

    await session.delete(user)
    await session.commit()
    await callback.message.edit_text("🗑 <b>Ваш аккаунт и все данные успешно и безвозвратно удалены.</b>\n\nЕсли захотите вернуться, просто отправьте /start.")
    await callback.answer()
