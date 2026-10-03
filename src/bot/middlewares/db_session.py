from typing import Any
from collections.abc import Callable, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from src.core.database import async_session_maker

class DbSessionMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any]
    ) -> Any:
        async with async_session_maker() as session:
            data['session'] = session
            return await handler(event, data)
