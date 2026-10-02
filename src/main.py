import asyncio
import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from aiogram.types import MenuButtonWebApp, WebAppInfo, BotCommand
from sqlalchemy import text
from src.core.config import settings
from src.core.database import engine, async_session_maker
from src.bot.bot import bot, dp
from src.api.v1.router import api_router
from src.services.category_service import CategoryService

from src.core.accrual_scheduler import accrual_background_loop

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure database schema is up-to-date with non-breaking migrations
    async with engine.begin() as conn:
        await conn.execute(text(
            "ALTER TABLE transactions ADD COLUMN IF NOT EXISTS related_transaction_id UUID REFERENCES transactions(id) ON DELETE SET NULL;"
        ))

    # Seed default system categories
    async with async_session_maker() as session:
        category_service = CategoryService(session)
        await category_service.seed_default_categories()

    # Configure Telegram Menu Button and Bot Commands for instant MiniApp access
    if settings.bot_token:
        try:
            domain = settings.domain
            if not domain or domain == "localhost":
                domain = "85.198.89.188.sslip.io:8443"
            elif ":" not in domain and "sslip.io" in domain:
                domain = f"{domain}:8443"
            miniapp_url = f"https://{domain}/app"

            me = await bot.get_me()
            if me and me.username:
                settings.bot_username = me.username

            await bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(
                    text="Menu",
                    web_app=WebAppInfo(url=miniapp_url)
                )
            )
            await bot.set_my_commands([
                BotCommand(command="miniapp", description="Открыть журнал транзакций"),
                BotCommand(command="deposits", description="Депозиты и сбережения"),
                BotCommand(command="family", description="Семейный бюджет"),
                BotCommand(command="start", description="Перезапустить бота"),
            ])
            logger.info("Chat menu button and bot commands successfully registered: %s", miniapp_url)
        except Exception as exc:
            logger.warning("Could not set chat menu button or commands: %s", exc)

    # Start monthly deposit interest accrual background scheduler
    accrual_task = asyncio.create_task(accrual_background_loop(async_session_maker))

    polling_task = None
    if settings.bot_token and settings.domain and settings.domain != "localhost" and ":" not in settings.domain:
        await bot.set_webhook(url=settings.webhook_url, secret_token=settings.webhook_secret)
    elif settings.bot_token:
        await bot.delete_webhook(drop_pending_updates=True)
        polling_task = asyncio.create_task(dp.start_polling(bot))

    yield

    accrual_task.cancel()
    if polling_task:
        polling_task.cancel()
    elif settings.bot_token and settings.domain and settings.domain != "localhost":
        await bot.delete_webhook()
    await engine.dispose()

app = FastAPI(title="Smart Bujet API", lifespan=lifespan)

app.include_router(api_router, prefix="/api/v1")

# Mount MiniApp static assets
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/app", include_in_schema=False)
    @app.get("/", include_in_schema=False)
    async def serve_miniapp():
        return FileResponse(os.path.join(static_dir, "index.html"))
