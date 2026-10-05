import unittest
import uuid
from unittest.mock import AsyncMock, MagicMock
from decimal import Decimal

try:
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    from src.bot.keyboards.inline import tx_toggle_keyboard
    from sqlalchemy.ext.asyncio import AsyncSession
    from src.models.transaction import Transaction
    from src.models.category import Category, CategoryType
    from src.models.user import User
    from src.models.alias import UserItemAlias
    from src.models.dynamic_context import DynamicFewShot, UserClassificationFeedback
    from src.services.dynamic_context_service import DynamicContextService
    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False


class TestTxToggleKeyboard(unittest.TestCase):
    def setUp(self):
        if not HAS_DEPS:
            self.skipTest("Dependencies not available in current environment")

    def test_keyboard_for_expense(self):
        tx = MagicMock(spec=Transaction)
        tx.id = uuid.uuid4()
        tx.type = CategoryType.expense if HAS_DEPS else "expense"

        kb = tx_toggle_keyboard(tx)
        self.assertIsNotNone(kb)
        btn = kb.inline_keyboard[0][0]
        self.assertEqual(btn.text, "🔄 Это доход")
        self.assertEqual(btn.callback_data, f"tx_toggle:{tx.id}")

    def test_keyboard_for_income(self):
        tx = MagicMock(spec=Transaction)
        tx.id = uuid.uuid4()
        tx.type = CategoryType.income if HAS_DEPS else "income"

        kb = tx_toggle_keyboard(tx)
        self.assertIsNotNone(kb)
        btn = kb.inline_keyboard[0][0]
        self.assertEqual(btn.text, "🔄 Это расход")
        self.assertEqual(btn.callback_data, f"tx_toggle:{tx.id}")

    def test_keyboard_for_batch(self):
        tx1 = MagicMock(spec=Transaction)
        tx1.id = uuid.uuid4()
        tx1.type = CategoryType.expense if HAS_DEPS else "expense"

        tx2 = MagicMock(spec=Transaction)
        tx2.id = uuid.uuid4()
        tx2.type = CategoryType.income if HAS_DEPS else "income"

        kb = tx_toggle_keyboard([tx1, tx2])
        self.assertIsNotNone(kb)
        self.assertEqual(len(kb.inline_keyboard), 2)
        self.assertEqual(kb.inline_keyboard[0][0].text, "🔄 #1 Это доход")
        self.assertEqual(kb.inline_keyboard[1][0].text, "🔄 #2 Это расход")


class TestDynamicContextService(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        if not HAS_DEPS:
            self.skipTest("Dependencies not available")
        self.session_mock = AsyncMock(spec=AsyncSession)
        self.service = DynamicContextService(self.session_mock)

    async def test_seed_default_few_shots(self):
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        self.session_mock.scalars.return_value = mock_scalars
        await self.service.seed_default_few_shots()
        self.assertTrue(self.session_mock.add_all.called)
        self.assertTrue(self.session_mock.commit.called)

    async def test_sanitize_poisoned_aliases(self):
        await self.service.sanitize_poisoned_aliases()
        self.assertTrue(self.session_mock.execute.called)
        self.assertTrue(self.session_mock.commit.called)

    def test_format_few_shots_prompt(self):
        shots = [{"query": "друг вернул долг 50000", "expected": {"type": "income"}}]
        formatted = self.service.format_few_shots_prompt(shots)
        self.assertIn("друг вернул долг", formatted)
        self.assertIn("income", formatted)


if __name__ == "__main__":
    unittest.main()
