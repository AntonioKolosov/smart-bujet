import io
from aiogram import Router, F, Bot
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession
from src.services.transaction_service import TransactionService

router = Router()

@router.message(F.voice)
async def process_voice_transaction(message: Message, session: AsyncSession, bot: Bot):
    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
    
    # In-memory buffer: no files saved to disk
    voice_buffer = io.BytesIO()
    await bot.download(message.voice.file_id, destination=voice_buffer)
    audio_bytes = voice_buffer.getvalue()

    tx_service = TransactionService(session)
    tx = await tx_service.process_voice(
        user_id=message.from_user.id,
        audio_bytes=audio_bytes,
        mime_type="audio/ogg"
    )

    type_label = "Расход" if tx.type == "expense" else "Доход"
    category_name = tx.category.name if tx.category else "Общее"

    await message.reply(
        f"🎙️ <b>{type_label} из аудиозаписи!</b>\n"
        f"📌 Позиция: <b>{tx.item_name}</b>\n"
        f"💰 Сумма: <b>{tx.amount:,.2f}</b>\n"
        f"📁 Категория: <b>{category_name}</b>"
    )

