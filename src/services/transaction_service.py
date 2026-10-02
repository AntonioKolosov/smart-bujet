from sqlalchemy.ext.asyncio import AsyncSession

class TransactionService:
    def __init__(self, session: AsyncSession):
        self.session = session

    # TODO: implement logic
