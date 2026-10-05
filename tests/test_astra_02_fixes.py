import unittest
import time
import math
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from src.core.security import validate_init_data
from src.services.ai_service import normalize_receipt_payload
from src.bot.messages import esc, format_amount, BotMessages
from src.models.category import CategoryType, Category
from src.models.asset import AssetAccount
from src.models.credit import CreditAccount
from src.models.transaction import Transaction
from src.services.credit_service import CreditService
from src.services.transaction_service import TransactionService


class TestAstra02SecurityFixes(unittest.TestCase):
    def test_empty_bot_token_rejected(self):
        # B01: empty or whitespace bot_token must fail closed
        res = validate_init_data("auth_date=1000000000&hash=dummy", "")
        self.assertIsNone(res)
        res_ws = validate_init_data("auth_date=1000000000&hash=dummy", "   ")
        self.assertIsNone(res_ws)

    def test_future_timestamp_rejected(self):
        # B01: future timestamp beyond 60s clock skew rejected
        future_auth = int(time.time()) + 300
        res = validate_init_data(f"auth_date={future_auth}&hash=dummy", "valid_token")
        self.assertIsNone(res)


class TestAstra02AIPayloadSanitization(unittest.TestCase):
    def test_string_false_rejected(self):
        # B08: string "false" must trigger non-financial guardrail
        raw_json = '{"is_financial": "false", "items": [{"item_name": "Тест", "amount": 100}]}'
        payload = normalize_receipt_payload(raw_json)
        self.assertFalse(payload["is_financial"])
        self.assertEqual(payload["items"], [])

    def test_nan_and_negative_amounts_filtered(self):
        # B08: NaN, Inf, <=0 amounts must be safely filtered out
        raw_json = '{"is_financial": true, "items": [{"item_name": "Valid", "amount": 500}, {"item_name": "NaN", "amount": "NaN"}, {"item_name": "Negative", "amount": -100}]}'
        payload = normalize_receipt_payload(raw_json)
        self.assertTrue(payload["is_financial"])
        self.assertEqual(len(payload["items"]), 1)
        self.assertEqual(payload["items"][0]["item_name"], "Valid")
        self.assertEqual(payload["items"][0]["amount"], 500.0)

    def test_negative_asset_amount_neutralized(self):
        # B08: negative or NaN asset_amount must be set to None
        raw_json = '{"is_financial": true, "items": [{"item_name": "Deposit", "amount": 50000, "asset_amount": -50}]}'
        payload = normalize_receipt_payload(raw_json)
        self.assertEqual(payload["items"][0]["asset_amount"], None)


class TestAstra02TelegramHTMLEscaping(unittest.TestCase):
    def test_html_tags_escaped(self):
        # C01: malicious or accidental HTML tags must be properly escaped
        raw = '<script>alert("xss")</script> & <b>bold</b>'
        escaped = esc(raw)
        self.assertNotIn("<script>", escaped)
        self.assertIn("&lt;script&gt;", escaped)
        self.assertIn("&amp;", escaped)

    def test_bot_messages_uses_escaping(self):
        tx = MagicMock(spec=Transaction)
        tx.type = CategoryType.expense
        tx.amount = 500.0
        tx.asset_amount = None
        tx.discount_amount = None
        tx.original_amount = None
        tx.item_name = 'Вредный <script>товар'
        tx.category = MagicMock(spec=Category)
        tx.category.name = 'Категория <b>Хак</b>'

        msg = BotMessages.tx_success(tx, currency="KZT", current_balance=10000.0)
        self.assertNotIn("<script>", msg)
        self.assertIn("&lt;script&gt;", msg)
        self.assertNotIn("<b>Хак</b>", msg)
        self.assertIn("&lt;b&gt;Хак&lt;/b&gt;", msg)


class TestAstra02CreditAtomicityAndReversal(unittest.IsolatedAsyncioTestCase):
    async def test_credit_service_auto_commit_false(self):
        # B04: auto_commit=False should flush and not commit
        session_mock = AsyncMock()
        service = CreditService(session_mock)

        await service.create_credit(
            user_id=1,
            name="Kaspi Credit",
            original_amount=Decimal("100000"),
            auto_commit=False
        )
        self.assertTrue(session_mock.add.called)
        self.assertTrue(session_mock.flush.called)
        self.assertFalse(session_mock.commit.called)

    async def test_delete_loan_repayment_capped_at_original_debt(self):
        # B10: restoring debt cannot exceed original debt principal
        session_mock = AsyncMock()
        tx_mock = MagicMock(spec=Transaction)
        tx_mock.user_id = 1
        tx_mock.credit_account_id = "credit-uuid"
        tx_mock.asset_account_id = None
        tx_mock.related_transaction_id = None
        tx_mock.type = CategoryType.expense
        tx_mock.amount = 150.0  # payment was 150

        credit_mock = MagicMock(spec=CreditAccount)
        credit_mock.original_amount = Decimal("100.0")
        credit_mock.remaining_amount = Decimal("0.0")  # debt was 0 after payment
        credit_mock.is_active = False

        session_mock.scalar.return_value = tx_mock
        session_mock.get.return_value = credit_mock

        service = TransactionService(session_mock)
        await service.delete_transaction(user_id=1, tx_id="tx-uuid")

        # Must be capped at original_amount (100.0), not 0 + 150 = 150.0
        self.assertEqual(credit_mock.remaining_amount, Decimal("100.0"))
        self.assertTrue(credit_mock.is_active)


if __name__ == "__main__":
    unittest.main()
