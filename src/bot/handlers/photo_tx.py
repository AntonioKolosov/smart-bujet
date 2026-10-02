import io
from aiogram import Router, F, Bot
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession
from src.services.transaction_service import TransactionService

router = Router()

@router.message(F.photo)
async def process_photo_transaction(message: Message, session: AsyncSession, bot: Bot):
    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")

    # In-memory buffer: no files saved to disk
    photo_buffer = io.BytesIO()
    # Download highest resolution photo
    await bot.download(message.photo[-1].file_id, destination=photo_buffer)
    image_bytes = photo_buffer.getvalue()

    tx_service = TransactionService(session)
    tx = await tx_service.process_receipt_photo(
        user_id=message.from_user.id,
        image_bytes=image_bytes,
        mime_type="image/jpeg"
    )

    type_label = "Расход" if tx.type == "expense" else "Доход"
    category_name = tx.category.name if tx.category else "Общее"

    await message.reply(
        f"🧾 <b>Чек распознан!</b>\n"
        f"📌 Позиция: <b>{tx.item_name}</b>\n"
        f"💰 Сумма: <b>{tx.amount:,.2f}</b>\n"
        f"📁 Категория: <b>{category_name}</b>"
    )

