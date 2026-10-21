import collections
import logging
import secrets
import time
from fastapi import APIRouter, Header, HTTPException, Request, status
from aiogram.types import Update
from src.bot.bot import dp, bot
from src.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

_PROCESSED_UPDATES = collections.OrderedDict()
_MAX_UPDATES = 5000
_UPDATE_TTL = 300  # 5 minutes


def is_duplicate_update(update_id: int) -> bool:
    now = time.time()
    while _PROCESSED_UPDATES and next(iter(_PROCESSED_UPDATES.values())) < now - _UPDATE_TTL:
        _PROCESSED_UPDATES.popitem(last=False)

    if update_id in _PROCESSED_UPDATES:
        return True
    _PROCESSED_UPDATES[update_id] = now
    if len(_PROCESSED_UPDATES) > _MAX_UPDATES:
        _PROCESSED_UPDATES.popitem(last=False)
    return False


@router.post("/webhook")
async def bot_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str = Header(None)
):
    if not settings.webhook_secret or not x_telegram_bot_api_secret_token or not secrets.compare_digest(x_telegram_bot_api_secret_token, settings.webhook_secret):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid secret token"
        )

    update_data = await request.json()
    update = Update(**update_data)

    if is_duplicate_update(update.update_id):
        logger.info("Discarding duplicate Telegram update: %s", update.update_id)
        return {"status": "ok", "duplicate": True}

    await dp.feed_webhook_update(bot, update)
    return {"status": "ok"}
