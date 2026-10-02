from sqlalchemy.ext.asyncio import AsyncSession

class ReportService:
    def __init__(self, session: AsyncSession):
        self.session = session
        
    # TODO: report generation logic
