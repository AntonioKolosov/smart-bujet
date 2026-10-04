import re
import logging
from aiogram import Router, F
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession
from src.services.transaction_service import TransactionService
from src.core.exceptions import InvalidTransactionAmountError, TransactionParseError, OffTopicMessageError
from src.models.user import User
from src.bot.messages import BotMessages
from src.bot.keyboards.inline import tx_toggle_keyboard

router = Router()
logger = logging.getLogger(__name__)

def try_parse_pure_amount(text: str) -> float | None:
    t = text.strip().lower()
    m = re.search(r"\b([0-9]+(?:[\s.,][0-9]{3})*(?:[.,][0-9]{1,2})?)\s*(тыс(?:\.|яч)?|k|к|тенге|руб|тг|kzt)?\b", t)
    if m:
        num_str = m.group(1).replace(" ", "").replace(",", ".")
        multiplier = 1000 if m.group(2) in ("тыс", "тысяч", "k", "к") else 1
        try:
            val = float(num_str) * multiplier
            ignored_words = {
                "у", "меня", "сейчас", "на", "счету", "счете", "баланс", "мой",
                "тыс", "тысяч", "k", "к", "тенге", "тг", "руб", "рублей", "kzt", "rub", "usd", "eur"
            }
            words = [w for w in re.findall(r"[а-яa-z]+", t) if w not in ignored_words]
            if len(words) <= 1:
                return val
        except ValueError:
            pass
    return None

@router.message(F.text & ~F.text.startswith('/'))
async def process_text_transaction(message: Message, session: AsyncSession):
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

    # Guard: if initial balance is not set yet
    if user.initial_balance is None:
        parsed_amount = try_parse_pure_amount(message.text)
        if parsed_amount is not None:
            user.initial_balance = parsed_amount
            await session.commit()
            await message.reply(BotMessages.initial_balance_set(parsed_amount, user.currency))
            return
        await message.reply(BotMessages.guard_set_balance_first())
        return

    tx_service = TransactionService(session)
    try:
        txs = await tx_service.process_text(user_id=message.from_user.id, text=message.text)
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
        await message.reply(BotMessages.off_topic_warning("text"))
    except (InvalidTransactionAmountError, TransactionParseError):
        await message.reply(BotMessages.text_clarification())
    except Exception as exc:
        logger.exception("Error processing text transaction: %s", exc)
        await message.reply(BotMessages.service_unavailable())

