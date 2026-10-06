from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from src.models.user import User
from src.bot.messages import format_summary_card
from src.bot.handlers.summary import on_summary_callback, summary_no_family_keyboard


class TestSummaryCardFormatting(unittest.TestCase):
    def setUp(self):
        self.summary = MagicMock()
        self.summary.currency = "KZT"
        self.summary.is_family = False
        self.summary.net_savings = 50000.0
        self.summary.saving_rate = 25.0
        self.summary.period_label = "Октябрь 2026"
        self.summary.total_expense = 150000.0
        self.summary.total_income = 200000.0
        self.summary.top_category_name = "Продукты"
        self.summary.top_category_amount = 60000.0
        self.summary.top_category_share = 40.0
        self.summary.current_liquid_balance = 300000.0
        self.summary.total_deposit_balance = 500000.0
        self.summary.total_credit_debt = 0.0
        self.summary.runway_months = 5.3

    def test_format_summary_card_default_uses_summary_period_label(self):
        card = format_summary_card(self.summary)
        self.assertIn("📅 Период: <b>Октябрь 2026</b>", card)

    def test_format_summary_card_on_demand_override(self):
        card = format_summary_card(self.summary, period_label="на текущую дату")
        self.assertIn("📅 Период: <b>на текущую дату</b>", card)
        self.assertNotIn("Октябрь 2026", card)

    def test_format_summary_card_scheduled_weekly_label(self):
        self.summary.period_label = "Неделя (05.10 - 11.10)"
        card = format_summary_card(self.summary)
        self.assertIn("📅 Период: <b>Неделя (05.10 - 11.10)</b>", card)


class TestSummaryFamilyGuard(unittest.IsolatedAsyncioTestCase):
    async def test_guard_triggers_for_user_without_family_group(self):
        session = AsyncMock()
        user = User(id=1, first_name="Тест", currency="KZT", family_group_id=None)
        session.get.return_value = user

        callback = AsyncMock()
        callback.data = "sum:scope:f"
        callback.from_user.id = 1
        callback.message = AsyncMock()

        await on_summary_callback(callback, session)

        # Ensure no database additions or commits occurred
        session.add.assert_not_called()
        session.commit.assert_not_called()

        # Check alert was answered
        callback.answer.assert_called_once_with(
            text="Вы не состоите в семейной группе",
            show_alert=True
        )

        # Check message was edited with guard message and no-family keyboard
        callback.message.edit_text.assert_called_once()
        text_arg = callback.message.edit_text.call_args[0][0]
        self.assertIn("Вы не состоите в семейной группе", text_arg)
        kb_arg = callback.message.edit_text.call_args[1]["reply_markup"]
        self.assertEqual(kb_arg, summary_no_family_keyboard())

    async def test_guard_triggers_for_solo_family_member(self):
        session = AsyncMock()
        user = User(id=2, first_name="Тест2", currency="KZT", family_group_id="group-uuid")
        session.get.return_value = user
        # Only 1 member in family group
        session.scalar.return_value = 1

        callback = AsyncMock()
        callback.data = "sum:scope:f"
        callback.from_user.id = 2
        callback.message = AsyncMock()

        await on_summary_callback(callback, session)

        callback.answer.assert_called_once_with(
            text="Вы не состоите в семейной группе",
            show_alert=True
        )
        text_arg = callback.message.edit_text.call_args[0][0]
        self.assertIn("Вы не состоите в семейной группе", text_arg)

    @patch("src.bot.handlers.summary.ReportService")
    @patch("src.bot.handlers.summary.AIService")
    async def test_personal_summary_renders_current_date_period_label(
        self, mock_ai_cls, mock_report_cls
    ):
        session = AsyncMock()
        user = User(id=3, first_name="Тест3", currency="KZT", family_group_id=None)
        session.get.return_value = user

        mock_report = AsyncMock()
        mock_summary = MagicMock()
        mock_summary.currency = "KZT"
        mock_summary.is_family = False
        mock_summary.net_savings = 10000.0
        mock_summary.saving_rate = 10.0
        mock_summary.period_label = "Октябрь 2026"
        mock_summary.total_expense = 90000.0
        mock_summary.total_income = 100000.0
        mock_summary.top_category_name = None
        mock_summary.current_liquid_balance = 50000.0
        mock_summary.total_deposit_balance = 0.0
        mock_summary.total_credit_debt = 0.0
        mock_summary.runway_months = 0.5
        mock_report.get_agent_analytics.return_value = mock_summary
        mock_report_cls.return_value = mock_report

        mock_ai = AsyncMock()
        mock_ai.generate_financial_advice.return_value = None
        mock_ai_cls.return_value = mock_ai

        callback = AsyncMock()
        callback.data = "sum:scope:p"
        callback.from_user.id = 3
        callback.message = AsyncMock()

        await on_summary_callback(callback, session)

        callback.message.edit_text.assert_called_once()
        text_arg = callback.message.edit_text.call_args[0][0]
        self.assertIn("📅 Период: <b>на текущую дату</b>", text_arg)
        self.assertNotIn("Октябрь 2026", text_arg)


if __name__ == "__main__":
    unittest.main()
