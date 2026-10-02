import argparse
import asyncio
from sqlalchemy import select
from src.core.database import async_session_maker
from src.models.user import User
from src.services.report_service import ReportService
from src.bot.bot import bot


async def run_reports(period: str = "week"):
    print(f"Generating and dispatching {period} reports...")
    async with async_session_maker() as session:
        users = (await session.scalars(select(User).where(User.is_active == True))).all()
        report_service = ReportService(session)

        for user in users:
            summary = await report_service.get_summary(
                user_id=user.id,
                family_group_id=user.family_group_id,
                period=period
            )

            if summary["total_income"] == 0 and summary["total_expense"] == 0:
                continue

            period_title = {"week": "Недельный", "month": "Месячный", "year": "Годовой"}.get(period, period)
            cats_text = "\n".join([f"• {c['category']}: {c['total']:,.2f} {user.currency}" for c in summary["categories"][:5]])

            msg = (
                f"📊 <b>{period_title} финансовый отчёт</b>\n\n"
                f"📈 Доходы: <b>+{summary['total_income']:,.2f} {user.currency}</b>\n"
                f"📉 Расходы: <b>-{summary['total_expense']:,.2f} {user.currency}</b>\n"
                f"⚖️ Баланс: <b>{summary['balance']:,.2f} {user.currency}</b>\n\n"
                f"<b>Топ категорий расходов:</b>\n{cats_text or 'Нет расходов'}"
            )

            try:
                await bot.send_message(chat_id=user.id, text=msg)
                print(f"Sent {period} report to user {user.id}")
            except Exception as e:
                print(f"Failed to send report to user {user.id}: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--period", choices=["week", "month", "year"], default="week")
    args = parser.parse_args()
    asyncio.run(run_reports(period=args.period))

