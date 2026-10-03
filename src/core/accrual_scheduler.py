import asyncio
import calendar
import logging
from datetime import datetime, timezone

from src.models.transaction import Transaction
from src.services.asset_service import AssetService

logger = logging.getLogger(__name__)


def is_last_day_of_month(target_dt: datetime) -> bool:
    """Returns True if target_dt is the last calendar day of its month (28/29, 30, or 31)."""
    _, last_day = calendar.monthrange(target_dt.year, target_dt.month)
    return target_dt.day == last_day


async def execute_accrual_check(
    session_maker,
    target_date: datetime | None = None
) -> list[Transaction]:
    """Execute monthly interest accrual across active deposit accounts."""
    async with session_maker() as session:
        service = AssetService(session)
        created_txs = await service.accrue_monthly_interest_for_all(target_date=target_date)
        if created_txs:
            logger.info("Successfully accrued interest for %d deposit accounts", len(created_txs))
        return created_txs


async def accrual_background_loop(session_maker, check_interval_seconds: int = 3600):
    """
    Background worker loop checking for month-end and accruing interest.
    Runs every hour by default.
    """
    logger.info("Starting deposit interest accrual background scheduler loop...")
    while True:
        try:
            now = datetime.now(datetime.UTC)
            # Accrue on the last day of the calendar month (28/29 in Feb, 30 or 31 in other months)
            if is_last_day_of_month(now):
                await execute_accrual_check(session_maker, target_date=now)
        except asyncio.CancelledError:
            logger.info("Accrual background scheduler cancelled.")
            break
        except Exception as exc:
            logger.error("Error in accrual background loop: %s", exc)

        try:
            await asyncio.sleep(check_interval_seconds)
        except asyncio.CancelledError:
            break
