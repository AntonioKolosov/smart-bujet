import io
import logging
from aiogram import Router, F, Bot
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession
from src.services.transaction_service import TransactionService
from src.core.exceptions import InvalidTransactionAmountError, TransactionParseError, OffTopicMessageError
from src.models.user import User
from src.bot.messages import BotMessages
from src.bot.keyboards.inline import tx_toggle_keyboard

router = Router()
logger = logging.getLogger(__name__)

@router.message(F.voice)
async def process_voice_transaction(message: Message, session: AsyncSession, bot: Bot):
    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
    
    voice_buffer = io.BytesIO()
    await bot.download(message.voice.file_id, destination=voice_buffer)
    audio_bytes = voice_buffer.getvalue()

    user = await session.get(User, message.from_user.id)
    if not user:
        user = User(
            id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            currency="KZT"
        )
        session.add(user)
        await session.commit()

    if user.initial_balance is None:
        await message.reply(BotMessages.guard_set_balance_first())
        return

    tx_service = TransactionService(session)
    try:
        txs = await tx_service.process_voice(
            user_id=message.from_user.id,
            audio_bytes=audio_bytes,
            mime_type="audio/ogg"
        )
        bal_data = await tx_service.get_user_balance(message.from_user.id)
        currency = user.currency or "KZT"
        await message.reply(
            BotMessages.tx_success(
                txs,
                currency=currency,
                current_balance=bal_data["current_balance"]
            ),
            reply_markup=tx_toggle_keyboard(txs)
        )
    except OffTopicMessageError:
        await message.reply(BotMessages.off_topic_warning("voice"))
    except InvalidTransactionAmountError as e:
        await message.reply(BotMessages.voice_clarification(recognized_text=e.raw_text))
    except TransactionParseError:
        await message.reply(BotMessages.voice_clarification())
    except Exception as exc:
        logger.exception("Error processing voice transaction: %s", exc)
        await message.reply(BotMessages.service_unavailable())

