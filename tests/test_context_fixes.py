import unittest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

from src.services.parser_service import ParserService

try:
    from sqlalchemy.ext.asyncio import AsyncSession
    from src.services.transaction_service import TransactionService, PARTNER_TRANSFER_REGEX
    from src.models.user import User
    from src.models.category import Category, CategoryType
    from src.models.transaction import Transaction
    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False


class TestContextParserAndRegex(unittest.TestCase):
    def test_parser_normal_expense(self):
        res = ParserService.parse_text("Манты 9600")
        self.assertIsNotNone(res)
        amt, name = res
        self.assertEqual(amt, Decimal("9600"))
        self.assertEqual(name, "Манты")

    def test_parser_bypasses_debt_returns_and_incomings(self):
        # "друг вернул 20000" must be bypassed to AI so it is classified as income, not expense
        self.assertIsNone(ParserService.parse_text("друг вернул 20000"))
        self.assertIsNone(ParserService.parse_text("вернули долг 15000"))
        self.assertIsNone(ParserService.parse_text("возврат 5000"))
        self.assertIsNone(ParserService.parse_text("мне пришел перевод 30000"))

    def test_parser_bypasses_transfers(self):
        # "Перевела 14000" must be bypassed to AI
        self.assertIsNone(ParserService.parse_text("Перевела 14000"))
        self.assertIsNone(ParserService.parse_text("я перевел 50000"))

    def test_partner_transfer_regex_strictness(self):
        if not HAS_DEPS:
            self.skipTest("Dependencies not available")
        # Explicit partner mentions match
        self.assertTrue(bool(PARTNER_TRANSFER_REGEX.search("перевел жене 50000")))
        self.assertTrue(bool(PARTNER_TRANSFER_REGEX.search("перевела мужу 14000")))
        self.assertTrue(bool(PARTNER_TRANSFER_REGEX.search("скинул партнеру 20000")))
        self.assertTrue(bool(PARTNER_TRANSFER_REGEX.search("супруге 30000")))

        # Generic transfers or unrelated family phrases do NOT match
        self.assertFalse(bool(PARTNER_TRANSFER_REGEX.search("перевела 14000")))
        self.assertFalse(bool(PARTNER_TRANSFER_REGEX.search("скинул 5000")))
        self.assertFalse(bool(PARTNER_TRANSFER_REGEX.search("друг вернул 20000")))


class TestPartnerDetection(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        if not HAS_DEPS:
            self.skipTest("Dependencies not available")

        self.session_mock = AsyncMock(spec=AsyncSession)
        self.user = MagicMock(spec=User)
        self.user.id = 1
        self.user.family_group_id = "group-uuid"

        self.partner = MagicMock(spec=User)
        self.partner.id = 2
        self.partner.family_group_id = "group-uuid"
        self.partner.first_name = "Тоша"
        self.partner.username = "tosha_user"

        self.session_mock.scalar = AsyncMock(return_value=self.partner)
        self.service = TransactionService(session=self.session_mock)

    async def test_generic_transfer_does_not_trigger_partner_detection(self):
        # "Перевела 14000" without mentioning partner must return None!
        result = await self.service._detect_family_partner(self.user, "Перевела 14000", "Денежный перевод")
        self.assertIsNone(result)

    async def test_generic_taxi_or_vendor_transfer_does_not_trigger_partner(self):
        result = await self.service._detect_family_partner(self.user, "Перевела 5000 за такси", "Перевод")
        self.assertIsNone(result)

    async def test_explicit_partner_mention_triggers_partner(self):
        result = await self.service._detect_family_partner(self.user, "Перевела мужу 14000", "Перевод")
        self.assertEqual(result, self.partner)

    async def test_partner_name_mention_triggers_partner(self):
        result = await self.service._detect_family_partner(self.user, "Скинула Тоше 20000", "Перевод")
        self.assertEqual(result, self.partner)


class TestIncomeCalculations(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        if not HAS_DEPS:
            self.skipTest("Dependencies not available")

        self.session_mock = AsyncMock(spec=AsyncSession)
        self.user = MagicMock(spec=User)
        self.user.id = 10
        self.user.initial_balance = 100000.0
        self.user.currency = "KZT"

        async def mock_get(model, id):
            if model == User:
                return self.user
            return None
        self.session_mock.get = AsyncMock(side_effect=mock_get)

    async def test_intra_family_mirror_excluded_from_month_income(self):
        service = TransactionService(session=self.session_mock)

        # Mock database scalar returns:
        # income_sum, liquid_income_sum, expense_sum, transfer_out_sum, transfer_in_sum, month_expense, month_income
        self.session_mock.scalar = AsyncMock(side_effect=[
            50000.0,  # income_sum (only external)
            50000.0,  # liquid_income_sum
            10000.0,  # expense_sum
            0.0,      # transfer_out_sum
            0.0,      # transfer_in_sum
            10000.0,  # month_expense
            50000.0,  # month_income (only external)
        ])

        bal = await service.get_user_balance(user_id=10)
        self.assertEqual(bal["month_income"], 50000.0)
        self.assertEqual(bal["month_expense"], 10000.0)
        self.assertEqual(bal["current_balance"], 140000.0)


if __name__ == "__main__":
    unittest.main()
