import logging
from aiogram import Router, F
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession
from src.services.transaction_service import TransactionService
from src.core.exceptions import InvalidTransactionAmountError, TransactionParseError
from src.bot.messages import BotMessages

router = Router()
logger = logging.getLogger(__name__)

@router.message(F.text & ~F.text.startswith('/'))
async def process_text_transaction(message: Message, session: AsyncSession):
    tx_service = TransactionService(session)
    try:
        tx = await tx_service.process_text(user_id=message.from_user.id, text=message.text)
        category_name = tx.category.name if tx.category else "Общее"
        await message.reply(
            BotMessages.tx_success(
                item_name=tx.item_name or message.text,
                amount=tx.amount,
                category_name=category_name,
                tx_type=tx.type.value
            )
        )
    except (InvalidTransactionAmountError, TransactionParseError):
        await message.reply(BotMessages.text_clarification())
    except Exception as exc:
        logger.error("Error processing text transaction: %s", exc, exc_info=True)
        await message.reply(BotMessages.service_unavailable())

