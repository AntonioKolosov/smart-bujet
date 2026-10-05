import io
import logging
import asyncio
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


class MediaGroupBuffer:
    """
    Buffers media group messages over an asyncio debounce window.
    Only the leader invocation proceeds with the collected album of messages,
    while follower invocations return early to avoid duplicate responses and race conditions.
    """
    def __init__(self, debounce_delay: float = 0.8, max_wait: float = 2.5):
        self.debounce_delay = debounce_delay
        self.max_wait = max_wait
        self._groups: dict[str, list[Message]] = {}
        self._last_arrival: dict[str, float] = {}
        self._lock = asyncio.Lock()

    async def add_and_wait(self, media_group_id: str, message: Message) -> list[Message] | None:
        loop = asyncio.get_running_loop()
        now = loop.time()
        async with self._lock:
            if media_group_id in self._groups:
                self._groups[media_group_id].append(message)
                self._last_arrival[media_group_id] = now
                return None
            self._groups[media_group_id] = [message]
            self._last_arrival[media_group_id] = now

        start_time = now
        while True:
            await asyncio.sleep(self.debounce_delay)
            async with self._lock:
                elapsed_since_last = loop.time() - self._last_arrival.get(media_group_id, 0)
                total_elapsed = loop.time() - start_time
                if elapsed_since_last >= self.debounce_delay or total_elapsed >= self.max_wait:
                    self._last_arrival.pop(media_group_id, None)
                    return self._groups.pop(media_group_id, [])


media_group_buffer = MediaGroupBuffer(debounce_delay=0.8, max_wait=2.5)


@router.message(F.photo)
async def process_photo_transaction(message: Message, session: AsyncSession, bot: Bot):
    if message.media_group_id:
        album = await media_group_buffer.add_and_wait(message.media_group_id, message)
        if album is None:
            return
        messages = album
    else:
        messages = [message]

    await bot.send_chat_action(chat_id=message.chat.id, action="typing")

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

    # Concurrent photo download for all images in the album
    async def _download_photo(msg: Message) -> bytes | None:
        if not msg.photo:
            return None
        buf = io.BytesIO()
        await bot.download(msg.photo[-1].file_id, destination=buf)
        return buf.getvalue()

    downloaded = await asyncio.gather(*(_download_photo(m) for m in messages))
    valid_images = [img for img in downloaded if img]
    if not valid_images:
        await message.reply(BotMessages.photo_clarification())
        return

    tx_service = TransactionService(session)
    currency = user.currency or "KZT"

    try:
        if len(valid_images) == 1:
            txs = await tx_service.process_receipt_photo(
                user_id=message.from_user.id,
                image_bytes=valid_images[0],
                mime_type="image/jpeg"
            )
            bal_data = await tx_service.get_user_balance(message.from_user.id)
            await message.reply(
                BotMessages.tx_success(
                    txs,
                    currency=currency,
                    current_balance=bal_data["current_balance"]
                ),
                reply_markup=tx_toggle_keyboard(txs)
            )
        else:
            batch_result = await tx_service.process_receipt_photos(
                user_id=message.from_user.id,
                images=valid_images,
                mime_type="image/jpeg"
            )
            bal_data = await tx_service.get_user_balance(message.from_user.id)
            await message.reply(
                BotMessages.receipt_batch_success(
                    receipts=batch_result["receipts"],
                    total_operations=batch_result["total_operations"],
                    total_amount=batch_result["total_amount"],
                    currency=currency,
                    current_balance=bal_data["current_balance"]
                ),
                reply_markup=tx_toggle_keyboard(batch_result["all_transactions"])
            )
    except OffTopicMessageError:
        await message.reply(BotMessages.off_topic_warning("photo"))
    except (InvalidTransactionAmountError, TransactionParseError):
        await message.reply(BotMessages.photo_clarification())
    except Exception as exc:
        logger.exception("Error processing receipt photo(s): %s", exc)
        await message.reply(BotMessages.service_unavailable())
