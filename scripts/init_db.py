import asyncio
from src.core.database import engine, async_session_maker
from src.models import Base
from src.services.category_service import CategoryService


async def init():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_session_maker() as session:
        service = CategoryService(session)
        await service.seed_default_categories()
    await engine.dispose()
    print("Database tables created and categories seeded successfully!")


if __name__ == "__main__":
    asyncio.run(init())
