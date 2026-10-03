import unittest
from datetime import datetime


def is_last_day_of_month_standalone(target_dt: datetime) -> bool:
    import calendar
    _, last_day = calendar.monthrange(target_dt.year, target_dt.month)
    return target_dt.day == last_day


class TestAccrualScheduler(unittest.TestCase):
    def test_is_last_day_of_month(self):
        # February leap year
        self.assertTrue(is_last_day_of_month_standalone(datetime(2024, 2, 29)))
        self.assertFalse(is_last_day_of_month_standalone(datetime(2024, 2, 28)))

        # February non-leap year
        self.assertTrue(is_last_day_of_month_standalone(datetime(2023, 2, 28)))

        # 30-day month (April)
        self.assertTrue(is_last_day_of_month_standalone(datetime(2024, 4, 30)))
        self.assertFalse(is_last_day_of_month_standalone(datetime(2024, 4, 29)))

        # 31-day month (October)
        self.assertTrue(is_last_day_of_month_standalone(datetime(2026, 10, 31)))
        self.assertFalse(is_last_day_of_month_standalone(datetime(2026, 10, 30)))


if __name__ == "__main__":
    unittest.main()
