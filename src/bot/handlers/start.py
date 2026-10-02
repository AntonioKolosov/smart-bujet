from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.models.user import User
from src.bot.keyboards.inline import currency_keyboard, welcome_back_keyboard
from src.bot.messages import BotMessages

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession):
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    
    user = await session.scalar(select(User).where(User.id == user_id))
    
    if not user:
        user = User(id=user_id, username=username, first_name=first_name, currency="RUB")
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

    await message.answer(
        BotMessages.welcome_back(first_name=user.first_name, currency=user.currency),
        reply_markup=welcome_back_keyboard()
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
        
    await callback.message.edit_text(
        BotMessages.currency_updated(currency),
        reply_markup=welcome_back_keyboard()
    )
    await callback.answer()
