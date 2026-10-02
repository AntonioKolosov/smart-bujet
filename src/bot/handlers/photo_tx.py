import io
import logging
from aiogram import Router, F, Bot
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession
from src.services.transaction_service import TransactionService
from src.core.exceptions import InvalidTransactionAmountError, TransactionParseError
from src.models.user import User
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
        txs = await tx_service.process_receipt_photo(
            user_id=message.from_user.id,
            image_bytes=image_bytes,
            mime_type="image/jpeg"
        )
        user = await session.get(User, message.from_user.id)
        currency = user.currency if user else "RUB"
        await message.reply(BotMessages.tx_success(txs, currency=currency))
    except (InvalidTransactionAmountError, TransactionParseError):
        await message.reply(BotMessages.photo_clarification())
    except Exception as exc:
        logger.error("Error processing receipt photo: %s", exc, exc_info=True)
        await message.reply(BotMessages.service_unavailable())

