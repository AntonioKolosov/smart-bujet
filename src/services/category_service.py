from sqlalchemy.ext.asyncio import AsyncSession

class CategoryService:
    def __init__(self, session: AsyncSession):
        self.session = session
        
    async def seed_default_categories(self):
        # TODO: seed system categories
        pass
