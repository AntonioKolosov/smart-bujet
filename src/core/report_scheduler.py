from __future__ import annotations

import asyncio
import calendar
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

try:
    from aiogram import Bot
    from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest
except ImportError:
    Bot = object  # type: ignore
    class TelegramForbiddenError(Exception): pass  # type: ignore
    class TelegramBadRequest(Exception): pass  # type: ignore
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.models.user import User
from src.models.report_log import ScheduledReportLog
from src.services.report_service import ReportService
from src.services.ai_service import AIService
from src.bot.messages import format_summary_card
from src.bot.handlers.summary import summary_inline_keyboard
from src.core.config import settings

logger = logging.getLogger(__name__)


def is_last_day_of_month(dt: datetime) -> bool:
    """Returns True if dt is the last calendar day of its month."""
    _, last_day = calendar.monthrange(dt.year, dt.month)
    return dt.day == last_day


def determine_broadcast_job(now: datetime) -> tuple[str, str] | None:
    """
    Evaluates trigger criteria with strict conflict precedence:
    Returns (report_type, period_key) or None.
    - Dec 31 19:00 -> yearly (precedence over monthly and weekly)
    - Last day of month 19:00 -> monthly (precedence over weekly)
    - Sunday 19:00 -> weekly
    """
    if now.hour != 19:
        return None

    # 1. Yearly Precedence (Dec 31, 19:00)
    if now.month == 12 and now.day == 31:
        return ("yearly", f"{now.year}")

    # 2. Monthly Precedence (Last day of month, 19:00)
    if is_last_day_of_month(now):
        return ("monthly", f"{now.year}-{now.month:02d}")

    # 3. Weekly Precedence (Sunday, 19:00)
    if now.weekday() == 6:
        week_num = now.isocalendar()[1]
        return ("weekly", f"{now.year}-W{week_num:02d}")

    return None


async def broadcast_scheduled_reports(
    session_maker: async_sessionmaker,
    bot: Bot,
    target_dt: datetime | None = None
) -> int:
    """
    Executes scheduled broadcast for all active users based on current time.
    Returns the number of reports sent.
    """
    tz_name = getattr(settings, "report_timezone", "Asia/Almaty")
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = ZoneInfo("UTC")

    now = target_dt or datetime.now(tz)
    job = determine_broadcast_job(now)
    if not job:
        return 0

    report_type, period_key = job
    period_map = {"weekly": "week", "monthly": "month", "yearly": "year"}
    period_code = period_map[report_type]

    logger.info("Starting scheduled financial broadcast: %s (%s)", report_type, period_key)

    async with session_maker() as session:
        users_res = await session.scalars(select(User).where(User.is_active.is_(True)))
        users = list(users_res.all())

        already_sent_res = await session.scalars(
            select(ScheduledReportLog.user_id).where(
                ScheduledReportLog.report_type == report_type,
                ScheduledReportLog.period_key == period_key
            )
        )
        sent_user_ids = set(already_sent_res.all())

    ai_service = AIService()
    sent_count = 0

    for user in users:
        if user.id in sent_user_ids:
            continue

        async with session_maker() as session:
            try:
                report_service = ReportService(session)
                summary = await report_service.get_agent_analytics(
                    user_id=user.id,
                    period=period_code,
                    ref_date=now
                )
                advice = await ai_service.generate_financial_advice(summary)

                period_name_ru = {"weekly": "Недельная", "monthly": "Месячная", "yearly": "Годовая"}.get(report_type, "")
                header = f"🔔 <b>{period_name_ru} сводка от Smart Bujet</b>\n\n"
                text = header + format_summary_card(summary, advice)
                kb = summary_inline_keyboard(
                    active_period=period_code,
                    active_scope="p",
                    has_family=bool(user.family_group_id)
                )

                await bot.send_message(chat_id=user.id, text=text, reply_markup=kb)

                log_entry = ScheduledReportLog(
                    user_id=user.id,
                    report_type=report_type,
                    period_key=period_key,
                    status="sent"
                )
                session.add(log_entry)
                await session.commit()
                sent_user_ids.add(user.id)
                sent_count += 1

            except TelegramForbiddenError:
                logger.info("Bot blocked by user %d. Marking status as blocked.", user.id)
                log_entry = ScheduledReportLog(
                    user_id=user.id,
                    report_type=report_type,
                    period_key=period_key,
                    status="blocked",
                    error_message="TelegramForbiddenError: Bot blocked by user"
                )
                session.add(log_entry)
                await session.commit()

            except TelegramBadRequest as exc:
                logger.warning("TelegramBadRequest for user %d: %s", user.id, exc)
                log_entry = ScheduledReportLog(
                    user_id=user.id,
                    report_type=report_type,
                    period_key=period_key,
                    status="failed",
                    error_message=str(exc)
                )
                session.add(log_entry)
                await session.commit()

            except Exception as exc:
                logger.error("Failed to deliver scheduled report to user %d: %s", user.id, exc)

        # Telegram broadcast throttle: 25 msg/sec
        await asyncio.sleep(0.04)

    return sent_count


async def report_scheduler_background_loop(
    session_maker: async_sessionmaker,
    bot: Bot,
    check_interval_seconds: int = 60
):
    """
    Background worker loop checking for scheduled broadcast triggers.
    Runs every minute by default.
    """
    logger.info("Starting scheduled financial report broadcast background scheduler loop...")
    while True:
        try:
            await broadcast_scheduled_reports(session_maker, bot)
        except asyncio.CancelledError:
            logger.info("Scheduled report broadcast scheduler cancelled.")
            break
        except Exception as exc:
            logger.error("Error in report broadcast background loop: %s", exc)

        try:
            await asyncio.sleep(check_interval_seconds)
        except asyncio.CancelledError:
            break
