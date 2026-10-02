from fastapi import APIRouter, Header, HTTPException, Request, status
from aiogram.types import Update
from src.bot.bot import dp, bot
from src.core.settings import settings

router = APIRouter()

@router.post("/webhook")
async def bot_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str = Header(None)
):
    if x_telegram_bot_api_secret_token != settings.WEBHOOK_SECRET:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid secret token"
        )
        
    update_data = await request.json()
    update = Update(**update_data)
    await dp.feed_webhook_update(bot, update)
    return {"status": "ok"}
