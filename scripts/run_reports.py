import argparse
import asyncio
from sqlalchemy import select
from src.core.database import async_session_maker
from src.models.user import User
from src.services.report_service import ReportService
from src.services.ai_service import AIService
from src.bot.messages import format_summary_card
from src.bot.handlers.summary import broadcast_digest_keyboard
from src.bot.bot import bot


async def run_reports(period: str = "week"):
    print(f"Generating and dispatching {period} reports with agent analytics...")
    ai_service = AIService()
    async with async_session_maker() as session:
        users = (await session.scalars(select(User).where(User.is_active == True))).all()
        report_service = ReportService(session)

        for user in users:
            summary = await report_service.get_agent_analytics(
                user_id=user.id,
                period=period
            )

            if summary.total_income == 0 and summary.total_expense == 0 and summary.total_deposit_balance == 0 and summary.total_credit_debt == 0:
                continue

            advice = await ai_service.generate_financial_advice(summary)
            msg = "🔔 <b>Плановая сводка от Smart Bujet</b>\n\n" + format_summary_card(summary, advice)
            kb = broadcast_digest_keyboard()

            try:
                await bot.send_message(chat_id=user.id, text=msg, reply_markup=kb)
                print(f"Sent {period} report to user {user.id}")
            except Exception as e:
                print(f"Failed to send report to user {user.id}: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--period", choices=["week", "month", "year"], default="week")
    args = parser.parse_args()
    asyncio.run(run_reports(period=args.period))
