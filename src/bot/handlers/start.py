from __future__ import annotations

import html
import io
import logging
import time
from collections import defaultdict
from aiogram import Router, F, Bot
from aiogram.filters import CommandStart, Command, CommandObject
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from src.models.user import User
from src.models.transaction import Transaction
from src.core.config import settings
from src.bot.keyboards.inline import (
    currency_keyboard,
    welcome_back_keyboard,
    miniapp_keyboard,
    deposits_keyboard,
    credits_keyboard,
    family_keyboard,
    analytics_keyboard,
    onboarding_choice_keyboard,
    statement_upload_keyboard,
    get_miniapp_url,
)
from src.bot.messages import BotMessages
from src.services.transaction_service import TransactionService
from src.services.family_service import FamilyService
from src.services.bank_statement_service import BankStatementService

logger = logging.getLogger(__name__)

router = Router()

# In-memory buffer for collecting multiple PDF statements during onboarding: user_id -> [(file_id, file_name)]
STATEMENT_BUFFER: dict[int, list[tuple[str, str]]] = defaultdict(list)


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


@router.message(Command("reset"))
async def cmd_reset(message: Message, session: AsyncSession):
    """Dev helper: Reset user's transactions and initial balance to test onboarding flow."""
    user_id = message.from_user.id
    user = await session.scalar(select(User).where(User.id == user_id))
    if user:
        user.initial_balance = None
        await session.execute(delete(Transaction).where(Transaction.user_id == user_id))
        await session.commit()
    STATEMENT_BUFFER.pop(user_id, None)

    await message.answer(
        "🔄 <b>Профиль сброшен для тестирования регистрации и выписок.</b>\n\n"
        "Как вы хотите начать вести учёт?",
        reply_markup=onboarding_choice_keyboard()
    )


@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession, command: CommandObject):
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    
    user = await session.scalar(select(User).where(User.id == user_id))
    is_new_user = False
    
    if not user:
        user = User(id=user_id, username=None, first_name=first_name, currency="KZT")
        session.add(user)
        await session.commit()
        is_new_user = True
    elif user.username is not None or user.first_name != first_name:
        user.username = None
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
            f"Добро пожаловать в <b>Smart Bujet</b>! Перед началом работы ознакомьтесь с правилами безопасности:\n\n"
            f"• 🔒 <b>Сквозное шифрование (AES-256-GCM):</b> названия ваших покупок, счетов и кредитов зашифрованы в базе данных.\n"
            f"• 🛡 <b>Guardrails-маскирование:</b> перед отправкой в AI имена, номера карт и телефоны обезличиваются.\n"
            f"• 🙈 <b>Слепота администратора:</b> ваш @username не сохраняется в базе данных.\n"
            f"• 🗑 <b>Право на удаление:</b> в любой момент команда /delete_account безвозвратно удаляет все ваши данные.\n\n"
            f"Нажимая кнопку ниже, вы соглашаетесь на обработку данных финансовым ассистентом.",
            reply_markup=privacy_kb
        )
        return

    # First-time onboarding fork: Start fresh vs Upload bank statements
    if user.initial_balance is None:
        STATEMENT_BUFFER.pop(user_id, None)
        await message.answer(
            f"👋 <b>Добро пожаловать в Smart Bujet, {user.first_name or ''}!</b>\n\n"
            f"Как вы хотите начать вести учёт?\n\n"
            f"• <b>🚀 Начать с нуля</b> — стандартная регистрация: выберите валюту и укажите текущий баланс.\n"
            f"• <b>📄 Загрузить историю</b> — отправьте одну или несколько банковских выписок (PDF), и бот автоматически восстановит историю, посчитает расходы и текущий баланс.",
            reply_markup=onboarding_choice_keyboard()
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


@router.callback_query(F.data == "onboard:fresh")
async def on_onboard_fresh(callback: CallbackQuery):
    STATEMENT_BUFFER.pop(callback.from_user.id, None)
    await callback.message.edit_text(
        "🚀 <b>Начало с нуля</b>\n\nВыберите основную валюту для ведения учёта:",
        reply_markup=currency_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "onboard:statement")
async def on_onboard_statement(callback: CallbackQuery):
    user_id = callback.from_user.id
    STATEMENT_BUFFER[user_id] = []
    await callback.message.edit_text(
        "📄 <b>Загрузка банковской выписки</b>\n\n"
        "Отправьте 1 или несколько PDF-файлов с выпиской из вашего банка (Kaspi, Halyk, Forte, Сбер, Тинькофф и др.).\n\n"
        "Вы можете прикрепить сразу несколько документов или отправлять их по очереди.\n"
        "Когда прикрепите файлы, нажмите <b>«Готово, обработать»</b>.",
        reply_markup=statement_upload_keyboard(collected_count=0)
    )
    await callback.answer()


@router.message(F.document, F.from_user.id.func(lambda uid: uid in STATEMENT_BUFFER))
async def handle_statement_pdf_upload(message: Message, session: AsyncSession):
    user_id = message.from_user.id
    if user_id not in STATEMENT_BUFFER:
        return

    doc = message.document
    if not doc:
        return

    is_pdf = bool(
        (doc.mime_type == "application/pdf")
        or (doc.file_name and doc.file_name.lower().endswith(".pdf"))
    )
    if not is_pdf:
        return

    file_name = doc.file_name or f"statement_{len(STATEMENT_BUFFER[user_id])+1}.pdf"
    STATEMENT_BUFFER[user_id].append((doc.file_id, file_name))
    count = len(STATEMENT_BUFFER[user_id])
    safe_name = html.escape(file_name)

    await message.answer(
        f"📎 <b>Файл выписки получен:</b> <code>{safe_name}</code>\n"
        f"Всего файлов подготовлено к обработке: <b>{count}</b>\n\n"
        f"Вы можете отправить ещё файлы или нажать кнопку ниже для обработки:",
        reply_markup=statement_upload_keyboard(collected_count=count)
    )


@router.callback_query(F.data == "statement:process")
async def on_statement_process(callback: CallbackQuery, session: AsyncSession, bot: Bot):
    user_id = callback.from_user.id
    files_meta = STATEMENT_BUFFER.pop(user_id, None)
    if not files_meta:
        await callback.answer("Прикрепите хотя бы один PDF-файл выписки", show_alert=True)
        return

    user = await session.scalar(select(User).where(User.id == user_id))
    if not user:
        user = User(
            id=user_id,
            username=None,
            first_name=callback.from_user.first_name,
            currency="KZT"
        )
        session.add(user)
        await session.commit()

    count = len(files_meta)
    await callback.message.edit_text(
        f"⏳ <b>Анализирую банковские выписки ({count} шт.) с помощью AI...</b>\n\n"
        f"Распознаю историю операций за весь период, даты, категории и остаток. "
        f"Для годовых выписок это может занять 15–40 секунд."
    )
    await callback.answer()

    downloaded: list[tuple[str, bytes]] = []
    try:
        for file_id, file_name in files_meta:
            buf = io.BytesIO()
            await bot.download(file_id, destination=buf)
            downloaded.append((file_name, buf.getvalue()))
    except Exception as exc:
        logger.error("Failed to download statement files: %s", exc)
        STATEMENT_BUFFER[user_id].extend(files_meta)
        await callback.message.answer(
            f"❌ Не удалось загрузить файлы из Telegram: {exc}\nПопробуйте ещё раз.",
            reply_markup=statement_upload_keyboard(collected_count=count)
        )
        return

    last_edit_ts = 0.0

    async def update_progress(status_text: str) -> None:
        nonlocal last_edit_ts
        now_ts = time.monotonic()
        if now_ts - last_edit_ts < 2.5:
            return
        last_edit_ts = now_ts
        try:
            await callback.message.edit_text(status_text)
        except Exception:
            pass

    statement_service = BankStatementService(session)
    try:
        result = await statement_service.import_statements(
            user_id=user.id,
            files=downloaded,
            progress_callback=update_progress,
        )
    except Exception as exc:
        logger.exception("Unhandled error during statement import for user %s: %s", user_id, exc)
        STATEMENT_BUFFER[user_id].extend(files_meta)
        await callback.message.answer(
            "❌ <b>Произошла техническая ошибка при разборе выписки.</b>\n"
            "Файлы сохранены в очереди — нажмите кнопку ниже, чтобы повторить попытку:",
            reply_markup=statement_upload_keyboard(collected_count=count)
        )
        return
    finally:
        downloaded.clear()

    if not result.get("success"):
        error_msg = result.get("error", "Не удалось распознать операции.")
        await callback.message.answer(
            f"❌ <b>Ошибка при обработке выписки:</b>\n{error_msg}\n\n"
            f"Вы можете попробовать отправить другой PDF-файл или начать с нуля:",
            reply_markup=onboarding_choice_keyboard()
        )
        return

    banks_str = html.escape(", ".join(result.get("bank_names", ["Банк"])))
    curr = result.get("currency", "KZT")
    summary_text = (
        f"✅ <b>Выписка успешно загружена и обработана!</b>\n\n"
        f"🏦 Банк: <b>{banks_str}</b>\n"
        f"📅 Период: <b>{result.get('period_label')}</b>\n"
        f"📊 Загружено операций: <b>{result.get('total_count')}</b>\n"
        f"💸 Расходы за весь период: <b>{result.get('total_expense', 0.0):,.2f} {curr}</b>\n"
        f"💰 Доходы за весь период: <b>{result.get('total_income', 0.0):,.2f} {curr}</b>\n\n"
        f"📌 <b>Состояние за текущий месяц:</b>\n"
        f"• Расходы в этом месяце: <b>{result.get('current_month_expense', 0.0):,.2f} {curr}</b>\n"
        f"• Доходы в этом месяце: <b>{result.get('current_month_income', 0.0):,.2f} {curr}</b>\n\n"
        f"💳 <b>Текущий баланс на счёте:</b> <b>{result.get('current_balance', 0.0):,.2f} {curr}</b>\n\n"
        f"🎉 История успешно сохранена! Теперь вы можете вести учёт в обычном режиме."
    )

    miniapp_url = get_miniapp_url()
    await callback.message.answer(
        summary_text,
        reply_markup=welcome_back_keyboard(miniapp_url=miniapp_url)
    )


@router.callback_query(F.data == "change_currency")
async def on_change_currency(callback: CallbackQuery):
    await callback.message.edit_text(
        "Выберите новую валюту:",
        reply_markup=currency_keyboard()
    )
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
        STATEMENT_BUFFER.pop(callback.from_user.id, None)
        await callback.message.edit_text(
            f"👋 <b>Добро пожаловать в Smart Bujet, {user.first_name if user else ''}!</b>\n\n"
            f"Как вы хотите начать вести учёт?\n\n"
            f"• <b>🚀 Начать с нуля</b> — стандартная регистрация: выберите валюту и укажите текущий баланс.\n"
            f"• <b>📄 Загрузить историю</b> — отправьте одну или несколько банковских выписок (PDF), и бот автоматически восстановит историю, посчитает расходы и текущий баланс.",
            reply_markup=onboarding_choice_keyboard()
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
