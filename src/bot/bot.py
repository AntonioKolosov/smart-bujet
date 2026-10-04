from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.utils.token import validate_token, TokenValidationError
from src.core.config import settings
from src.bot.handlers import start, text_tx, voice_tx, photo_tx, family, tx_actions
from src.bot.middlewares.db_session import DbSessionMiddleware

DUMMY_FALLBACK_TOKEN = "123456789:TEST_BOT_TOKEN_FOR_INIT_TESTS"


def _resolve_bot_token() -> str:
    candidate = (settings.bot_token or "").strip()
    try:
        if candidate and validate_token(candidate):
            return candidate
    except (TokenValidationError, Exception) as exc:
        import logging
        logging.getLogger(__name__).warning("Token validation failed: %s", exc)
    return DUMMY_FALLBACK_TOKEN


bot = Bot(
    token=_resolve_bot_token(),
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher()
dp.update.middleware(DbSessionMiddleware())

dp.include_router(start.router)
dp.include_router(tx_actions.router)
dp.include_router(text_tx.router)
dp.include_router(voice_tx.router)
dp.include_router(photo_tx.router)
dp.include_router(family.router)

