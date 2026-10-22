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
from src.services.bank_statement_service import (
    BankStatementService,
    clean_gemini_json,
    extract_rows_locally,
    extract_statement_metadata_regex,
)
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

    def test_local_regex_parses_kaspi_and_halyk_statements(self):
        sample_text = (
            "--- СТРАНИЦА 1 ---\n"
            "АО «Народный Банк Казахстана»\n"
            "Выписка по счету за период с 14.01.2025 по 22.10.2026\n"
            "Валюта счета: KZT\n"
            "Входящий остаток: 0,00 KZT\n"
            "Исходящий остаток: 3 389,00 KZT\n"
            "Дата проведения Дата обработки Описание операции Сумма операции Валюта Приход Расход Комиссия\n"
            "14.01.2025 15.01.2025 Оплата товаров и услуг MAGNUM.AF31.KSO ALMATY KZ -4 500,00 KZT 0,00 -4 500,00 0,00\n"
            "16.01.2025 16.01.2025 Оплата товаров и услуг MAGNUM CASHCARRY AF 41 KS -2 300,00 KZT 0,00 -2 300,00 0,00\n"
            "31.01.2025 31.01.2025 Зачисление заработной платы ТОО Мобайл Телеком - Сервис 550 000,21 KZT 550 000,21 0,00 0,00\n"
            "05.02.2025 - 1 200,00 ₸ Покупка YANDEX.GO\n"
            "06.02.2025 - 100 000,00 ₸ Перевод На Kaspi Депозит\n"
        )
        meta = extract_statement_metadata_regex(sample_text)
        self.assertEqual(meta["bank_name"], "Halyk Bank")
        self.assertEqual(meta["currency"], "KZT")
        self.assertEqual(meta["period_start"], "2025-01-14")
        self.assertEqual(meta["period_end"], "2026-10-22")
        self.assertEqual(meta["closing_balance"], 3389.0)

        rows, unparsed = extract_rows_locally(sample_text)
        self.assertEqual(len(unparsed), 0)
        self.assertEqual(len(rows), 4)  # Deposit transfer excluded
        self.assertEqual(rows[0]["item_name"], "Magnum")
        self.assertEqual(rows[1]["item_name"], "Magnum")
        self.assertEqual(rows[2]["type"], "income")
        self.assertEqual(rows[2]["amount"], 550000.21)
        self.assertEqual(rows[3]["item_name"], "Yandex Go")

    async def test_hybrid_parser_deduplicates_merchants_into_single_ai_call(self):
        session = AsyncMock()
        service = BankStatementService(session, api_key="test_key")
        service.client = MagicMock()

        sample_chunk = (
            "Kaspi Gold\n"
            "За период с 01.01.2026 по 22.10.2026\n"
            "Доступно на 22.10.2026: 3 389,00 ₸\n"
            "10.01.26 - 5 000,00 ₸ Покупка MAGNUM.AF31.KSO\n"
            "11.01.26 - 7 000,00 ₸ Покупка MAGNUM CASHCARRY\n"
            "12.01.26 - 3 500,00 ₸ Покупка IP ALTAEV ZH.A.\n"
            "13.01.26 - 4 200,00 ₸ Покупка IP ALTAEV ZH.A.\n"
        )
        with patch(
            "src.services.bank_statement_service.extract_and_redact_pdf_chunks",
            return_value=([sample_chunk], False),
        ):
            service._call_gemini_chunk = AsyncMock(
                return_value={
                    "bank_name": "Kaspi Bank",
                    "currency": "KZT",
                    "closing_balance": 3389.0,
                    "merchants": {"0": "Еда вне дома"},
                }
            )
            res = await service.parse_single_pdf(b"pdf", "kaspi.pdf", user_id=101)
            # Only 1 AI call made for the 1 unknown merchant (IP ALTAEV ZH.A.), while Magnum was resolved locally
            self.assertEqual(service._call_gemini_chunk.await_count, 1)
            self.assertEqual(res["closing_balance"], 3389.0)
            self.assertEqual(len(res["transactions"]), 4)
            self.assertEqual(res["transactions"][0]["category"], "Продукты")
            self.assertEqual(res["transactions"][1]["category"], "Продукты")
            self.assertEqual(res["transactions"][2]["category"], "Еда вне дома")
            self.assertEqual(res["transactions"][3]["category"], "Еда вне дома")

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

            added_txs = [call[0][0] for call in session.add.call_args_list if isinstance(call[0][0], Transaction)]
            self.assertEqual(len(added_txs), 3)
            for tx in added_txs:
                self.assertIsNone(tx.raw_text)
                self.assertEqual(tx.user_id, 123)

            self.assertEqual(user.initial_balance, Decimal("50000.0"))
            session.commit.assert_awaited()

    async def test_negative_initial_balance_calibration_when_cashflow_exceeds_closing_balance(self):
        session = AsyncMock()
        user = User(id=339, username=None, first_name="Test", currency="KZT", initial_balance=None)
        session.get.side_effect = lambda m, pk: user if (m == User and pk == 339) else None

        cat_salary = Category(id=1, name="Зарплата", type=CategoryType.income)
        cat_food = Category(id=2, name="Продукты", type=CategoryType.expense)

        with patch("src.services.bank_statement_service.CategoryService") as MockCatService, \
             patch("src.services.bank_statement_service.TransactionService") as MockTxService:
            MockCatService.return_value.get_categories = AsyncMock(return_value=[cat_salary, cat_food])
            MockTxService.return_value.get_user_balance = AsyncMock(return_value={"current_balance": 3389.0})

            statement_service = BankStatementService(session)
            statement_service.parse_single_pdf = AsyncMock(return_value={
                "bank_name": "Halyk Bank",
                "currency": "KZT",
                "period_start": "2025-01-14",
                "period_end": "2026-10-22",
                "closing_balance": 3389.0,
                "transactions": [
                    {"date": "2026-01-31", "amount": 18498983.68, "type": "income", "item_name": "Зарплата", "category": "Зарплата"},
                    {"date": "2026-02-15", "amount": 16543341.97, "type": "expense", "item_name": "Magnum", "category": "Продукты"},
                ],
            })

            res = await statement_service.import_statements(user_id=339, files=[("halyk.pdf", b"pdf")])
            self.assertTrue(res["success"])
            self.assertEqual(res["current_balance"], 3389.0)
            self.assertEqual(user.initial_balance, Decimal("-1952252.71"))


if __name__ == "__main__":
    unittest.main()
