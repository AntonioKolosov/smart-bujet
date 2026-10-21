import unittest
import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from src.models.asset import AssetAccount, AssetType
from src.models.category import Category, CategoryType
from src.models.transaction import Transaction, TransactionSource
from src.models.user import User
from src.services.ai_service import AIService, AIRateLimiter
from src.services.transaction_service import TransactionService
from src.api.v1.webhook import is_duplicate_update
from src.bot.keyboards.inline import tx_toggle_keyboard


class TestArgonSecurity(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.session = AsyncMock()
        self.ai_service = AIService()
        self.user = User(
            id=12345678,
            first_name="Тест",
            currency="KZT",
            initial_balance=100000.0,
            family_group_id=None
        )

    def test_ai_rate_limiter(self):
        limiter = AIRateLimiter(max_per_minute=3, max_per_day=5)
        user_id = 999999

        allowed1, _ = limiter.check_and_record(user_id)
        allowed2, _ = limiter.check_and_record(user_id)
        allowed3, _ = limiter.check_and_record(user_id)
        self.assertTrue(allowed1)
        self.assertTrue(allowed2)
        self.assertTrue(allowed3)

        # 4th call exceeds per-minute quota
        allowed4, msg = limiter.check_and_record(user_id)
        self.assertFalse(allowed4)
        self.assertIn("минутный лимит", msg)

    def test_webhook_deduplication(self):
        update_id = 1234567
        # First arrival is not duplicate
        self.assertFalse(is_duplicate_update(update_id))
        # Immediate duplicate arrival is detected
        self.assertTrue(is_duplicate_update(update_id))

    def test_tx_toggle_keyboard_always_has_back_to_menu(self):
        """Test that tx_toggle_keyboard always includes 'Вернуться в меню'."""
        # 1. Single expense
        tx_exp = Transaction(id=uuid.uuid4(), amount=1000.0, type=CategoryType.expense)
        kb_exp = tx_toggle_keyboard(tx_exp)
        self.assertIsNotNone(kb_exp)
        # Row 1: toggle, Row 2: back to menu
        self.assertEqual(len(kb_exp.inline_keyboard), 2)
        self.assertEqual(kb_exp.inline_keyboard[0][0].text, "🔄 Это доход")
        self.assertEqual(kb_exp.inline_keyboard[1][0].text, "📋 Вернуться в меню")
        self.assertEqual(kb_exp.inline_keyboard[1][0].callback_data, "sum:back:main")

        # 2. Transfer out (e.g. cash deposit / currency purchase)
        tx_transfer = Transaction(id=uuid.uuid4(), amount=640000.0, type=CategoryType.transfer_out)
        kb_transfer = tx_toggle_keyboard(tx_transfer)
        self.assertIsNotNone(kb_transfer)
        # Sole Row: back to menu
        self.assertEqual(len(kb_transfer.inline_keyboard), 1)
        self.assertEqual(kb_transfer.inline_keyboard[0][0].text, "📋 Вернуться в меню")
        self.assertEqual(kb_transfer.inline_keyboard[0][0].callback_data, "sum:back:main")

    async def test_update_transaction_currency_division_formula(self):
        """
        Verify that editing a currency transaction amount uses division:
        new_asset_amt = new_amount / exchange_rate
        instead of multiplying base amount by exchange rate!
        """
        tx_service = TransactionService(self.session)

        asset = AssetAccount(
            id=uuid.uuid4(),
            user_id=self.user.id,
            name="Наличная валюта",
            type=AssetType.currency,
            currency="USD",
            balance=100.0
        )

        tx = Transaction(
            id=uuid.uuid4(),
            user_id=self.user.id,
            category_id=1,
            amount=45000.0,
            asset_amount=100.0,
            exchange_rate=450.0,
            type=CategoryType.transfer_out,
            asset_account_id=asset.id,
            item_name="Покупка валюты"
        )

        self.session.scalar = AsyncMock(return_value=tx)
        self.session.get = AsyncMock(side_effect=lambda model, mid, *args, **kwargs: asset if model == AssetAccount else tx)

        from src.schemas.transaction import TransactionUpdate
        # Change amount from 45000 to 90000 KZT (should yield 200 USD at 450 rate, not 40 500 000 USD!)
        update_data = TransactionUpdate(amount=Decimal("90000.00"))

        await tx_service.update_transaction(tx_id=tx.id, user_id=self.user.id, data=update_data)

        # 90000 / 450 = 200 USD
        self.assertEqual(tx.asset_amount, 200.0)
        # Asset balance delta: +100 USD -> 100 + 100 = 200 USD
        self.assertEqual(asset.balance, 200.0)

    async def test_raw_text_minimization_on_transaction_creation(self):
        """
        Verify that raw_text is set to None on transaction creation (data minimization).
        """
        tx_service = TransactionService(self.session)
        self.session.get = AsyncMock(return_value=self.user)
        self.session.scalar = AsyncMock(return_value=Category(id=1, name="Продукты", type=CategoryType.expense))
        tx_service.credit_service.get_user_credits = AsyncMock(return_value=[])
        tx_service._save_alias = AsyncMock()

        added_objects = []
        self.session.add = MagicMock(side_effect=lambda o: added_objects.append(o))
        self.session.commit = AsyncMock()

        with patch("src.services.transaction_service.ParserService.parse_text", return_value=(Decimal("2500"), "молоко")), \
             patch.object(tx_service, "_get_alias_category", return_value=Category(id=1, name="Продукты", type=CategoryType.expense)):
            txs = await tx_service.process_text(user_id=self.user.id, text="молоко 2500")

        self.assertEqual(len(txs), 1)
        self.assertIsNone(txs[0].raw_text)


if __name__ == "__main__":
    unittest.main()
