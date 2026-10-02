from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.models.user import User
from src.bot.keyboards.inline import currency_keyboard

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession):
    user_id = message.from_user.id
    username = message.from_user.username
    
    user = await session.scalar(select(User).where(User.id == user_id))
    
    if not user:
        user = User(id=user_id, username=username, first_name=message.from_user.first_name, currency="RUB")
        session.add(user)
        await session.commit()
    
    await message.answer(
        "Добро пожаловать в Smart Bujet! Пожалуйста, выберите валюту по умолчанию:",
        reply_markup=currency_keyboard()
    )

@router.callback_query(F.data.startswith("currency_"))
async def process_currency(callback: CallbackQuery, session: AsyncSession):
    currency = callback.data.split("_")[1]
    user_id = callback.from_user.id
    
    user = await session.scalar(select(User).where(User.id == user_id))
    if user:
        user.currency = currency
        await session.commit()
        
    await callback.message.edit_text(f"Валюта успешно установлена: {currency}")
    await callback.answer()
