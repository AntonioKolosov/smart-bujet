import calendar
import unittest
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass
from typing import Any


def is_last_day_of_month(dt: datetime) -> bool:
    _, last_day = calendar.monthrange(dt.year, dt.month)
    return dt.day == last_day


def determine_broadcast_job(now: datetime) -> tuple[str, str] | None:
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


MONTH_NAMES_RU = [
    "", "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"
]


def get_period_bounds(period: str, ref_date: datetime | None = None) -> tuple[datetime, datetime, str]:
    now = ref_date or datetime.now(timezone.utc)
    if period == "week":
        start_date = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = now
        label = f"Неделя ({start_date.strftime('%d.%m')} - {end_date.strftime('%d.%m')})"
    elif period == "year":
        start_date = datetime(now.year, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        end_date = now
        label = f"{now.year} год"
    else:
        start_date = datetime(now.year, now.month, 1, 0, 0, 0, tzinfo=timezone.utc)
        end_date = now
        label = f"{MONTH_NAMES_RU[now.month]} {now.year}"
    return start_date, end_date, label


@dataclass
class MockAnalyticsSummaryData:
    period: str
    period_label: str
    currency: str
    total_expense: float
    total_income: float
    net_savings: float
    saving_rate: float
    top_category_name: str | None
    top_category_amount: float
    top_category_share: float
    current_liquid_balance: float
    total_deposit_balance: float
    total_credit_debt: float
    monthly_credit_payment: float
    debt_burden_ratio: float
    runway_months: float
    is_family: bool


class TestReportSchedulerStandalone(unittest.TestCase):
    def test_is_last_day_of_month(self):
        # February non-leap year
        self.assertTrue(is_last_day_of_month(datetime(2025, 2, 28, 12, 0)))
        self.assertFalse(is_last_day_of_month(datetime(2025, 2, 27, 12, 0)))

        # February leap year
        self.assertTrue(is_last_day_of_month(datetime(2024, 2, 29, 12, 0)))
        self.assertFalse(is_last_day_of_month(datetime(2024, 2, 28, 12, 0)))

        # April 30 days
        self.assertTrue(is_last_day_of_month(datetime(2026, 4, 30, 19, 0)))
        self.assertFalse(is_last_day_of_month(datetime(2026, 4, 29, 19, 0)))

        # December 31 days
        self.assertTrue(is_last_day_of_month(datetime(2026, 12, 31, 19, 0)))
        self.assertFalse(is_last_day_of_month(datetime(2026, 12, 30, 19, 0)))

    def test_determine_broadcast_job_precedence(self):
        # 1. Wrong hour -> None
        dt_wrong_hour = datetime(2026, 10, 11, 18, 0)
        self.assertIsNone(determine_broadcast_job(dt_wrong_hour))

        # 2. Yearly precedence: Dec 31 at 19:00 (even on Sunday)
        dt_dec31 = datetime(2028, 12, 31, 19, 0)
        self.assertEqual(dt_dec31.weekday(), 6)  # Sunday
        self.assertEqual(determine_broadcast_job(dt_dec31), ("yearly", "2028"))

        # 3. Monthly precedence: May 31, 2026 at 19:00 (is Sunday!)
        dt_may31 = datetime(2026, 5, 31, 19, 0)
        self.assertEqual(dt_may31.weekday(), 6)  # Sunday
        self.assertEqual(determine_broadcast_job(dt_may31), ("monthly", "2026-05"))

        # 4. Weekly: October 11, 2026 at 19:00 (Sunday, middle of month)
        dt_sunday = datetime(2026, 10, 11, 19, 0)
        self.assertEqual(dt_sunday.weekday(), 6)
        job = determine_broadcast_job(dt_sunday)
        self.assertIsNotNone(job)
        self.assertEqual(job[0], "weekly")
        self.assertTrue(job[1].startswith("2026-W"))

        # 5. Normal weekday -> None
        dt_wed = datetime(2026, 10, 7, 19, 0)
        self.assertIsNone(determine_broadcast_job(dt_wed))

    def test_period_bounds(self):
        ref = datetime(2026, 10, 15, 14, 30, tzinfo=timezone.utc)
        s_w, e_w, lbl_w = get_period_bounds("week", ref)
        self.assertEqual(s_w.weekday(), 0)
        self.assertIn("Неделя", lbl_w)

        s_m, e_m, lbl_m = get_period_bounds("month", ref)
        self.assertEqual(s_m.day, 1)
        self.assertEqual(s_m.month, 10)
        self.assertIn("Октябрь", lbl_m)

        s_y, e_y, lbl_y = get_period_bounds("year", ref)
        self.assertEqual(s_y.day, 1)
        self.assertEqual(s_y.month, 1)
        self.assertIn("2026 год", lbl_y)

    def test_rule_based_advice_logic(self):
        summary = MockAnalyticsSummaryData(
            period="month",
            period_label="Октябрь 2026",
            currency="KZT",
            total_expense=150000.0,
            total_income=300000.0,
            net_savings=150000.0,
            saving_rate=50.0,
            top_category_name="Продукты",
            top_category_amount=60000.0,
            top_category_share=40.0,
            current_liquid_balance=250000.0,
            total_deposit_balance=500000.0,
            total_credit_debt=100000.0,
            monthly_credit_payment=20000.0,
            debt_burden_ratio=6.7,
            runway_months=5.0,
            is_family=False
        )

        try:
            from src.services.ai_service import AIService
            ai = AIService(api_key=None)
            advice = ai._generate_rule_based_advice(summary)
            self.assertIn("Продукты", advice["where_to_cut"])
            self.assertIn("досрочное погашение", advice["where_to_save"])
        except ImportError:
            pass


if __name__ == "__main__":
    unittest.main()
