import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from src.core.config import settings
from src.core.database import engine, async_session_maker
from src.bot.bot import bot, dp
from src.api.v1.router import api_router
from src.services.category_service import CategoryService

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Seed default system categories
    async with async_session_maker() as session:
        category_service = CategoryService(session)
        await category_service.seed_default_categories()

    polling_task = None
    if settings.bot_token and settings.domain and settings.domain != "localhost":
        await bot.set_webhook(url=settings.webhook_url, secret_token=settings.webhook_secret)
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
