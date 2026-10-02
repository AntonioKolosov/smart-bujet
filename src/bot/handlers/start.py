from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.models.user import User
from src.core.config import settings
from src.bot.keyboards.inline import currency_keyboard, welcome_back_keyboard, miniapp_keyboard
from src.bot.messages import BotMessages
from src.services.transaction_service import TransactionService

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

@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession):
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    
    user = await session.scalar(select(User).where(User.id == user_id))
    
    if not user:
        user = User(id=user_id, username=username, first_name=first_name, currency="KZT")
        session.add(user)
        await session.commit()
        await message.answer(
            BotMessages.welcome_new(),
            reply_markup=currency_keyboard()
        )
        return
    
    # Update first_name/username if changed
    if user.username != username or user.first_name != first_name:
        user.username = username
        user.first_name = first_name
        await session.commit()

    if user.initial_balance is None:
        await message.answer(
            f"👋 <b>С возвращением, {user.first_name or ''}!</b>\n\n{BotMessages.ask_initial_balance()}"
        )
        return

    tx_service = TransactionService(session)
    bal_data = await tx_service.get_user_balance(user.id)
    miniapp_url = get_miniapp_url()

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
        tx_service = TransactionService(session)
        bal_data = await tx_service.get_user_balance(user_id)
        await callback.message.edit_text(
            BotMessages.currency_updated(currency),
            reply_markup=welcome_back_keyboard(miniapp_url=miniapp_url)
        )
    await callback.answer()
