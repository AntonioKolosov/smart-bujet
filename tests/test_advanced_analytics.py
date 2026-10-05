import unittest
from datetime import datetime, timezone
from uuid import uuid4
from src.schemas.analytics import MonthlyAnalyticsResponse, SafetyCushionMetrics, MonthlyTrendItem
from src.services.report_service import ESSENTIAL_CATEGORIES, ReportService

class TestAdvancedAnalytics(unittest.TestCase):
    def test_essential_categories_taxonomy(self):
        """Verify standard 50/30/20 essential categories set."""
        self.assertIn("Продукты", ESSENTIAL_CATEGORIES)
        self.assertIn("Обязательные расходы", ESSENTIAL_CATEGORIES)
        self.assertIn("Здоровье", ESSENTIAL_CATEGORIES)
        self.assertIn("Транспорт", ESSENTIAL_CATEGORIES)
        self.assertIn("Погашение кредита", ESSENTIAL_CATEGORIES)
        self.assertIn("Ребёнок", ESSENTIAL_CATEGORIES)
        self.assertIn("Образование", ESSENTIAL_CATEGORIES)
        self.assertIn("Питомец", ESSENTIAL_CATEGORIES)

        # Wants / Discretionary should NOT be in essentials
        self.assertNotIn("Еда вне дома", ESSENTIAL_CATEGORIES)
        self.assertNotIn("Развлечения", ESSENTIAL_CATEGORIES)
        self.assertNotIn("Шоппинг", ESSENTIAL_CATEGORIES)
        self.assertNotIn("Подписки", ESSENTIAL_CATEGORIES)
        self.assertNotIn("Подарок", ESSENTIAL_CATEGORIES)

    def test_monthly_analytics_schema_validation(self):
        """Verify Pydantic schema validation for new analytics fields."""
        payload = {
            "currency": "KZT",
            "months_count": 6,
            "history": [
                {
                    "year": 2026,
                    "month": 9,
                    "label": "Сен",
                    "total_expense": 250000.0,
                    "total_income": 350000.0,
                    "net_savings": 100000.0,
                    "cumulative_savings": 100000.0,
                    "cushion_balance": 400000.0,
                    "essential_expense": 125000.0,
                    "discretionary_expense": 125000.0,
                    "essential_percent": 50.0,
                    "discretionary_percent": 50.0,
                },
                {
                    "year": 2026,
                    "month": 10,
                    "label": "Окт",
                    "total_expense": 280000.0,
                    "total_income": 350000.0,
                    "net_savings": 70000.0,
                    "cumulative_savings": 170000.0,
                    "cushion_balance": 470000.0,
                    "essential_expense": 154000.0,
                    "discretionary_expense": 126000.0,
                    "essential_percent": 55.0,
                    "discretionary_percent": 45.0,
                }
            ],
            "metrics": {
                "current_month_spend": 280000.0,
                "monthly_average_spend": 265000.0,
                "top_category_name": "Продукты",
                "top_category_amount": 95000.0,
                "top_category_percent": 33.9,
                "current_month_net_savings": 70000.0,
                "current_month_essential_percent": 55.0,
            },
            "cushion": {
                "current_cushion": 470000.0,
                "target_cushion_3m": 795000.0,
                "target_cushion_6m": 1590000.0,
                "runway_months": 1.8,
                "status": "warning"
            }
        }
        res = MonthlyAnalyticsResponse.model_validate(payload)
        self.assertEqual(res.currency, "KZT")
        self.assertEqual(len(res.history), 2)
        self.assertEqual(res.history[0].net_savings, 100000.0)
        self.assertEqual(res.history[0].essential_percent, 50.0)
        self.assertIsNotNone(res.cushion)
        self.assertEqual(res.cushion.status, "warning")
        self.assertEqual(res.metrics.current_month_net_savings, 70000.0)

if __name__ == "__main__":
    unittest.main()
