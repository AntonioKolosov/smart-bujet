import json
from fastapi import Depends, HTTPException, status, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.core.database import get_db
from src.core.config import settings
from src.core.security import validate_init_data
from src.models.user import User

async def get_current_user(
    init_data: str = Header(..., alias="X-Telegram-Init-Data"),
    session: AsyncSession = Depends(get_db)
) -> User:
    validated = validate_init_data(init_data, settings.bot_token)
    if not validated or "user" not in validated:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired Telegram initData"
        )

    try:
        user_info = json.loads(validated["user"])
        telegram_id = int(user_info["id"])
    except (KeyError, ValueError, json.JSONDecodeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed user payload in initData"
        )

    user = await session.scalar(select(User).where(User.id == telegram_id))
    if not user:
        user = User(
            id=telegram_id,
            username=user_info.get("username"),
            first_name=user_info.get("first_name"),
            currency="RUB"
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

    return user

