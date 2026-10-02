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

@router.message(F.voice)
async def process_voice_transaction(message: Message, session: AsyncSession, bot: Bot):
    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
    
    voice_buffer = io.BytesIO()
    await bot.download(message.voice.file_id, destination=voice_buffer)
    audio_bytes = voice_buffer.getvalue()

    tx_service = TransactionService(session)
    try:
        tx = await tx_service.process_voice(
            user_id=message.from_user.id,
            audio_bytes=audio_bytes,
            mime_type="audio/ogg"
        )
        category_name = tx.category.name if tx.category else "Общее"
        await message.reply(
            BotMessages.tx_success(
                item_name=tx.item_name or "Позиция",
                amount=tx.amount,
                category_name=category_name,
                tx_type=tx.type.value
            )
        )
    except InvalidTransactionAmountError as e:
        await message.reply(BotMessages.voice_clarification(recognized_text=e.raw_text))
    except TransactionParseError:
        await message.reply(BotMessages.voice_clarification())
    except Exception as exc:
        logger.error("Error processing voice transaction: %s", exc, exc_info=True)
        await message.reply(BotMessages.service_unavailable())

