import asyncio
import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from aiogram.types import MenuButtonWebApp, WebAppInfo
from src.core.config import settings
from src.core.database import engine, async_session_maker
from src.bot.bot import bot, dp
from src.api.v1.router import api_router
from src.services.category_service import CategoryService

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Seed default system categories
    async with async_session_maker() as session:
        category_service = CategoryService(session)
        await category_service.seed_default_categories()

    polling_task = None
    if settings.bot_token and settings.domain and settings.domain != "localhost":
        await bot.set_webhook(url=settings.webhook_url, secret_token=settings.webhook_secret)
        # Configure Telegram Menu Button for instant MiniApp access
        try:
            miniapp_url = f"https://{settings.domain}/app"
            await bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(
                    text="Транзакции 💳",
                    web_app=WebAppInfo(url=miniapp_url)
                )
            )
        except Exception as exc:
            logger.warning("Could not set chat menu button: %s", exc)
    elif settings.bot_token:
        await bot.delete_webhook(drop_pending_updates=True)
        polling_task = asyncio.create_task(dp.start_polling(bot))

    yield

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
