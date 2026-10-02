from aiogram import Router, F
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

router = Router()

@router.message(F.text & ~F.text.startswith('/'))
async def process_text_transaction(message: Message, session: AsyncSession):
    # TODO: parse amount+item, find category, create transaction
    await message.reply("Транзакция добавлена! (заглушка)")
