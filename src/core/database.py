from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.core.config import settings

try:
    engine = create_async_engine(settings.database_url, echo=False)
    async_session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
except Exception:
    engine = None
    async_session_maker = None

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    if async_session_maker is not None:
        async with async_session_maker() as session:
            yield session
