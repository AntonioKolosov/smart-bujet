import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
from decimal import Decimal
import uuid

from src.bot.keyboards.inline import (
    onboarding_choice_keyboard,
    statement_upload_keyboard,
    tx_toggle_keyboard,
)
from src.services.bank_statement_service import BankStatementService, clean_gemini_json
from src.models.user import User
from src.models.category import Category, CategoryType
from src.models.transaction import Transaction


class TestBankStatementImport(unittest.IsolatedAsyncioTestCase):
    def test_onboarding_keyboards(self):
        kb = onboarding_choice_keyboard()
        self.assertEqual(len(kb.inline_keyboard), 1)
        self.assertEqual(len(kb.inline_keyboard[0]), 2)
        self.assertEqual(kb.inline_keyboard[0][0].callback_data, "onboard:fresh")
        self.assertEqual(kb.inline_keyboard[0][1].callback_data, "onboard:statement")

        upload_kb = statement_upload_keyboard(collected_count=2)
        self.assertEqual(len(upload_kb.inline_keyboard), 2)
        self.assertEqual(upload_kb.inline_keyboard[0][0].callback_data, "statement:process")
        self.assertIn("2 файлов", upload_kb.inline_keyboard[0][0].text)

    def test_tx_toggle_keyboard_has_menu_button(self):
        tx = MagicMock(spec=Transaction)
        tx.id = uuid.uuid4()
        tx.type = CategoryType.expense
        kb = tx_toggle_keyboard(tx)
        self.assertIsNotNone(kb)
        self.assertEqual(len(kb.inline_keyboard), 2)
        self.assertIn("меню", kb.inline_keyboard[1][0].text.lower())
        self.assertEqual(kb.inline_keyboard[1][0].callback_data, "sum:back:main")

    def test_clean_gemini_json(self):
        raw = "```json\n{\"bank_name\": \"Kaspi\", \"closing_balance\": 50000}\n```"
        parsed = clean_gemini_json(raw)
        self.assertEqual(parsed.get("bank_name"), "Kaspi")
        self.assertEqual(parsed.get("closing_balance"), 50000)

    def test_clean_gemini_json_salvages_truncated_output(self):
        truncated = (
            '{"bank_name": "Kaspi Bank", "currency": "KZT", "closing_balance": 95000.0, "transactions": ['
            '{"date": "2025-01-10", "amount": 4500.0, "type": "expense", "item_name": "Magnum", "category": "Продукты"}, '
            '{"date": "2025-01-11", "amount": 1200.0, "type": "expen'
        )
        parsed = clean_gemini_json(truncated)
        self.assertEqual(parsed.get("bank_name"), "Kaspi Bank")
        self.assertEqual(parsed.get("closing_balance"), 95000.0)
        self.assertEqual(len(parsed.get("transactions", [])), 1)
        self.assertEqual(parsed["transactions"][0]["item_name"], "Magnum")

    async def test_parse_single_pdf_merges_multiple_chunks_and_checks_rate_limiter(self):
        session = AsyncMock()
        service = BankStatementService(session, api_key="test_key")
        service.client = MagicMock()

        with patch(
            "src.services.bank_statement_service.extract_and_redact_pdf_chunks",
            return_value=(["chunk_1", "chunk_2"], False),
        ):
            service._call_gemini_chunk = AsyncMock(
                side_effect=[
                    {
                        "bank_name": "Kaspi Bank",
                        "currency": "KZT",
                        "period_start": "2025-01-01",
                        "period_end": "2025-06-30",
                        "closing_balance": 120000.0,
                        "transactions": [{"date": "2025-02-01", "amount": 5000.0, "type": "expense", "item_name": "A"}],
                    },
                    {
                        "period_end": "2025-12-31",
                        "transactions": [{"date": "2025-11-01", "amount": 7000.0, "type": "expense", "item_name": "B"}],
                    },
                ]
            )
            merged = await service.parse_single_pdf(b"pdf", "year.pdf", user_id=999, known_names=["Test"])
            self.assertEqual(merged["bank_name"], "Kaspi Bank")
            self.assertEqual(merged["period_end"], "2025-12-31")
            self.assertEqual(len(merged["transactions"]), 2)

    async def test_bank_statement_import_calibrates_balance_and_records_history(self):
        session = AsyncMock()
        user = User(id=123, username="testuser", first_name="Test", currency="KZT", initial_balance=None)

        def session_get_side_effect(model, pk):
            if model == User and pk == 123:
                return user
            return None
        session.get.side_effect = session_get_side_effect

        cat_food = Category(id=1, name="Продукты", type=CategoryType.expense)
        cat_salary = Category(id=2, name="Зарплата", type=CategoryType.income)
        cat_other = Category(id=3, name="Прочее", type=CategoryType.expense)

        with patch("src.services.bank_statement_service.CategoryService") as MockCatService, \
             patch("src.services.bank_statement_service.TransactionService") as MockTxService:

            cat_service_instance = MockCatService.return_value
            cat_service_instance.get_all_categories = AsyncMock(return_value=[cat_food, cat_salary, cat_other])
            cat_service_instance.get_categories = AsyncMock(return_value=[cat_food, cat_salary, cat_other])

            tx_service_instance = MockTxService.return_value
            tx_service_instance.get_user_balance = AsyncMock(return_value={
                "current_balance": 180000.0,
                "month_expense": 20000.0,
                "month_income": 0.0,
            })

            statement_service = BankStatementService(session)

            mock_statement_payload = {
                "bank_name": "Kaspi Bank",
                "currency": "KZT",
                "period_start": "2024-01-01",
                "period_end": "2026-10-21",
                "starting_balance": 50000.0,
                "closing_balance": 180000.0,
                "transactions": [
                    {
                        "date": "2024-02-15",
                        "amount": 10000.0,
                        "type": "expense",
                        "item_name": "Magnum",
                        "category": "Продукты",
                    },
                    {
                        "date": "2025-05-10",
                        "amount": 160000.0,
                        "type": "income",
                        "item_name": "Зарплата ТОО",
                        "category": "Зарплата",
                    },
                    {
                        "date": "2026-10-15",
                        "amount": 20000.0,
                        "type": "expense",
                        "item_name": "Yandex Go",
                        "category": "Транспорт",
                    },
                ],
            }

            statement_service.parse_single_pdf = AsyncMock(return_value=mock_statement_payload)

            result = await statement_service.import_statements(
                user_id=123,
                files=[("kaspi_2024_2026.pdf", b"fake_pdf_content")],
            )

            self.assertTrue(result["success"])
            self.assertEqual(result["total_count"], 3)
            self.assertEqual(result["total_expense"], 30000.0)
            self.assertEqual(result["total_income"], 160000.0)
            self.assertEqual(result["current_balance"], 180000.0)
            self.assertIn("Kaspi Bank", result["bank_names"])

            # Verify transactions added to session with raw_text=None
            added_txs = [call[0][0] for call in session.add.call_args_list if isinstance(call[0][0], Transaction)]
            self.assertEqual(len(added_txs), 3)
            for tx in added_txs:
                self.assertIsNone(tx.raw_text)
                self.assertEqual(tx.user_id, 123)

            # Net cashflow: +160,000 - 30,000 = +130,000
            # Closing balance = 180,000
            # Initial balance should be 180,000 - 130,000 = 50,000
            self.assertEqual(user.initial_balance, Decimal("50000.0"))
            session.commit.assert_awaited()


if __name__ == "__main__":
    unittest.main()
