from contextlib import asynccontextmanager
from fastapi import FastAPI
from src.core.settings import settings
from src.core.database import engine
from src.bot.bot import bot, dp
from src.api.v1.router import api_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Set webhook on startup
    webhook_url = f"{settings.WEBHOOK_DOMAIN}/api/v1/webhook"
    await bot.set_webhook(url=webhook_url, secret_token=settings.WEBHOOK_SECRET)
    yield
    # Cleanup on shutdown
    await bot.delete_webhook()
    await engine.dispose()

app = FastAPI(title="Smart Bujet API", lifespan=lifespan)

app.include_router(api_router, prefix="/api/v1")
