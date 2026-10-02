from fastapi import Depends, HTTPException, status, Header
from sqlalchemy.ext.asyncio import AsyncSession
from src.core.database import get_db
from src.models.user import User

async def get_current_user(
    init_data: str = Header(..., alias="X-Telegram-Init-Data"),
    session: AsyncSession = Depends(get_db)
) -> User:
    # TODO: Validate initData via aiogram/hmac, extract user ID, return User
    # For now, placeholder implementation
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not implemented")
