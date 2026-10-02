from aiogram import Router, F
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

router = Router()

@router.message(F.photo)
async def process_photo_transaction(message: Message, session: AsyncSession):
    # TODO: photo parsing logic
    await message.reply("Обработка фото в разработке.")
