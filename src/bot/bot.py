from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from src.core.config import settings
from src.bot.handlers import start, text_tx, voice_tx, photo_tx, family
from src.bot.middlewares.db_session import DbSessionMiddleware

bot = Bot(
    token=settings.bot_token or "123456789:AAG_placeholder_token_for_init",
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher()
dp.update.middleware(DbSessionMiddleware())

dp.include_router(start.router)
dp.include_router(text_tx.router)
dp.include_router(voice_tx.router)
dp.include_router(photo_tx.router)
dp.include_router(family.router)
