from sqlalchemy.ext.asyncio import AsyncSession

class FamilyService:
    def __init__(self, session: AsyncSession):
        self.session = session

    # TODO: logic
