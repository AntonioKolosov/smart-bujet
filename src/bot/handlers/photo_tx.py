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

@router.message(F.photo)
async def process_photo_transaction(message: Message, session: AsyncSession, bot: Bot):
    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")

    photo_buffer = io.BytesIO()
    await bot.download(message.photo[-1].file_id, destination=photo_buffer)
    image_bytes = photo_buffer.getvalue()

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
        txs = await tx_service.process_receipt_photo(
            user_id=message.from_user.id,
            image_bytes=image_bytes,
            mime_type="image/jpeg"
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
        await message.reply(BotMessages.off_topic_warning("photo"))
    except (InvalidTransactionAmountError, TransactionParseError):
        await message.reply(BotMessages.photo_clarification())
    except Exception as exc:
        logger.exception("Error processing receipt photo: %s", exc)
        await message.reply(BotMessages.service_unavailable())

