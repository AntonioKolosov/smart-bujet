import io
import logging
from aiogram import Router, F, Bot
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession
from src.services.transaction_service import TransactionService
from src.core.exceptions import InvalidTransactionAmountError, TransactionParseError
from src.bot.messages import BotMessages

router = Router()
logger = logging.getLogger(__name__)

@router.message(F.photo)
async def process_photo_transaction(message: Message, session: AsyncSession, bot: Bot):
    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")

    photo_buffer = io.BytesIO()
    await bot.download(message.photo[-1].file_id, destination=photo_buffer)
    image_bytes = photo_buffer.getvalue()

    tx_service = TransactionService(session)
    try:
        tx = await tx_service.process_receipt_photo(
            user_id=message.from_user.id,
            image_bytes=image_bytes,
            mime_type="image/jpeg"
        )
        category_name = tx.category.name if tx.category else "Общее"
        await message.reply(
            BotMessages.tx_success(
                item_name=tx.item_name or "Чек",
                amount=tx.amount,
                category_name=category_name,
                tx_type=tx.type.value
            )
        )
    except (InvalidTransactionAmountError, TransactionParseError):
        await message.reply(BotMessages.photo_clarification())
    except Exception as exc:
        logger.error("Error processing receipt photo: %s", exc, exc_info=True)
        await message.reply(BotMessages.service_unavailable())

