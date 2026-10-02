from aiogram import Router, F
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

router = Router()

@router.message(F.voice)
async def process_voice_transaction(message: Message, session: AsyncSession):
    # TODO: voice processing logic
    await message.reply("Голосовая транзакция в разработке.")
