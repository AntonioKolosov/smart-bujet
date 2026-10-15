import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import uuid
from decimal import Decimal
from datetime import datetime, timezone

from src.services.pii_guardrail_service import PIIGuardrailService
from src.services.ai_service import normalize_receipt_payload, AIService
from src.services.asset_service import AssetService
from src.services.report_service import ReportService
from src.services.transaction_service import TransactionService
from src.models.user import User
from src.models.asset import AssetAccount, AssetType
from src.models.credit import CreditAccount
from src.models.category import Category, CategoryType
from src.models.transaction import Transaction, TransactionSource


class TestGuardrailsPII(unittest.TestCase):
    def test_pii_masking_and_unmasking(self):
        session = PIIGuardrailService.create_session()
        assets_ctx = [
            {"id": "c9cba288-2c85-41c3-acaf-7f9e099b2e7b", "name": "Депозит Айганым", "type": "deposit", "currency": "USD"}
        ]
        credits_ctx = [
            {"id": "7ae8666a-1234-5678-90ab-cdef12345678", "name": "Халыковский кредит", "remaining_amount": 50000.0, "monthly_payment": 15000.0, "currency": "KZT"}
        ]

        masked_assets = PIIGuardrailService.mask_assets_context(assets_ctx, session)
        masked_credits = PIIGuardrailService.mask_credits_context(credits_ctx, session)

        self.assertEqual(masked_assets[0]["id"], "[СЧЕТ_1]")
        self.assertEqual(masked_assets[0]["name"], "[СЧЕТ_1]")
        self.assertEqual(masked_credits[0]["id"], "[КРЕДИТ_1]")
        self.assertEqual(masked_credits[0]["name"], "[КРЕДИТ_1]")

        # Test text masking with cards, phone, IIN, and names
        input_text = "Оплатил 15000 на Халыковский кредит с карты 4400 1234 5678 9012, телефон +7 701 123 45 67, ИИН 950101350123 Айганым"
        masked_text = PIIGuardrailService.mask_text(input_text, session, known_names=["Айганым"])

        self.assertNotIn("4400 1234 5678 9012", masked_text)
        self.assertNotIn("+7 701 123 45 67", masked_text)
        self.assertNotIn("950101350123", masked_text)
        self.assertNotIn("Халыковский кредит", masked_text)
        self.assertIn("[КАРТА_1]", masked_text)
        self.assertIn("[ТЕЛЕФОН_1]", masked_text)
        self.assertIn("[ИИН_1]", masked_text)
        self.assertIn("[КРЕДИТ_1]", masked_text)
        self.assertIn("[ИМЯ_1]", masked_text)

        # Test unmasking of LLM payload
        mock_llm_payload = {
            "items": [
                {
                    "category": "Погашение кредита",
                    "type": "expense",
                    "amount": 15000.0,
                    "item_name": "Погашение [КРЕДИТ_1] [ИМЯ_1]",
                    "credit_account_id": "[КРЕДИТ_1]",
                    "target_credit_name": "[КРЕДИТ_1]",
                    "raw_text": masked_text
                }
            ]
        }
        unmasked = PIIGuardrailService.unmask_payload(mock_llm_payload, session)
        item = unmasked["items"][0]
        self.assertEqual(item["credit_account_id"], "7ae8666a-1234-5678-90ab-cdef12345678")
        self.assertEqual(item["target_credit_name"], "Халыковский кредит")
        self.assertIn("Халыковский кредит", item["item_name"])
        self.assertIn("Айганым", item["item_name"])


class TestNormalizeReceiptPayload(unittest.TestCase):
    def test_retains_credit_repayment_without_amount(self):
        raw_json = """
        {
            "is_financial": true,
            "items": [
                {
                    "category": "Погашение кредита",
                    "type": "expense",
                    "credit_action": "repay",
                    "target_credit_name": "Халык кредит"
                }
            ]
        }
        """
        payload = normalize_receipt_payload(raw_json)
        self.assertEqual(len(payload["items"]), 1)
        self.assertEqual(payload["items"][0]["amount"], 0.0)


class TestCreditMonthlyPaymentAutoFill(unittest.IsolatedAsyncioTestCase):
    async def test_autofill_from_monthly_payment(self):
        session = AsyncMock()
        tx_service = TransactionService(session)

        dummy_credit = CreditAccount(
            id=uuid.uuid4(),
            user_id=123,
            name="Халыковский кредит",
            original_amount=100000.0,
            remaining_amount=80000.0,
            currency="KZT",
            monthly_payment=25000.0,
            is_active=True
        )

        tx_service.credit_service.get_user_credits = AsyncMock(return_value=[dummy_credit])
        tx_service.credit_service.resolve_credit_account = AsyncMock(return_value=dummy_credit)

        # 1. Test when LLM returns item with amount=0
        raw_items = [{
            "category": "Погашение кредита",
            "type": "expense",
            "amount": 0.0,
            "credit_action": "repay",
            "target_credit_name": "Халыковский кредит"
        }]
        res = await tx_service._try_autofill_credit_payment(123, "оплатил ежемесячный платеж", raw_items)
        self.assertEqual(res[0]["amount"], 25000.0)
        self.assertEqual(res[0]["target_credit_name"], "Халыковский кредит")

        # 2. Test when LLM returned empty items but text expresses monthly payment intent
        res_empty = await tx_service._try_autofill_credit_payment(123, "оплатил ежемесячный платеж Халыковский кредит", [])
        self.assertEqual(len(res_empty), 1)
        self.assertEqual(res_empty[0]["amount"], 25000.0)
        self.assertEqual(res_empty[0]["credit_action"], "repay")


class TestAssetLiquidationAndFX(unittest.IsolatedAsyncioTestCase):
    async def test_delete_asset_positive_balance_creates_liquidation_transfer(self):
        session = AsyncMock()
        service = AssetService(session)

        asset_id = uuid.uuid4()
        user = User(id=123, currency="KZT", initial_balance=50000.0)
        asset = AssetAccount(
            id=asset_id,
            user_id=123,
            name="Наличная валюта",
            type=AssetType.currency,
            currency="USD",
            balance=100.0,
            is_active=True
        )

        service.get_asset_by_id = AsyncMock(return_value=asset)
        session.get = AsyncMock(return_value=user)
        service.category_service.find_by_name = AsyncMock(return_value=Category(id=1, name="Снятие с депозита", type=CategoryType.transfer_in))

        added_objects = []
        session.add = MagicMock(side_effect=lambda obj: added_objects.append(obj))

        success = await service.delete_asset(123, asset_id, liquidation_rate=450.0)
        self.assertTrue(success)

        # Verify liquidation transaction was created
        txs = [o for o in added_objects if isinstance(o, Transaction)]
        self.assertEqual(len(txs), 1)
        liq_tx = txs[0]
        self.assertEqual(liq_tx.type, CategoryType.transfer_in)
        self.assertEqual(liq_tx.amount, 45000.0)
        self.assertEqual(liq_tx.asset_amount, 100.0)
        self.assertEqual(liq_tx.exchange_rate, 450.0)

    async def test_deposit_to_foreign_currency_asset(self):
        session = AsyncMock()
        service = AssetService(session)

        asset_id = uuid.uuid4()
        user = User(id=123, currency="KZT")
        asset = AssetAccount(
            id=asset_id,
            user_id=123,
            name="Роды",
            type=AssetType.deposit,
            currency="USD",
            balance=0.0,
            is_active=True
        )

        session.get = AsyncMock(side_effect=lambda model, mid: asset if model == AssetAccount else user)
        service.category_service.get_categories = AsyncMock(return_value=[Category(id=2, name="Депозит и вклады", type=CategoryType.transfer_out)])

        added_objects = []
        session.add = MagicMock(side_effect=lambda obj: added_objects.append(obj))

        await service.deposit_to_asset(user_id=123, asset_id=asset_id, amount=100.0, exchange_rate=450.0)

        self.assertEqual(asset.balance, 100.0)
        txs = [o for o in added_objects if isinstance(o, Transaction)]
        self.assertEqual(len(txs), 1)
        tx = txs[0]
        self.assertEqual(tx.amount, 45000.0)  # Converted to KZT
        self.assertEqual(tx.asset_amount, 100.0)  # 100 USD
        self.assertEqual(tx.exchange_rate, 450.0)


class TestIntraFamilyAnalyticsExclusion(unittest.IsolatedAsyncioTestCase):
    async def test_analytics_excludes_related_transactions(self):
        session = AsyncMock()
        service = ReportService(session)

        # Mock query results
        session.scalar = AsyncMock(return_value=0.0)
        session.execute = AsyncMock()
        mock_result = MagicMock()
        mock_result.all.return_value = []
        session.execute.return_value = mock_result

        # Call get_category_breakdown in personal mode (family_group_id=None)
        res = await service.get_category_breakdown(user_id=123, family_group_id=None)
        self.assertIn("categories", res)
        # Verify execute was called with conditions excluding related transactions
        call_args = session.execute.call_args[0][0]
        sql_str = str(call_args)
        self.assertIn("related_transaction_id IS NULL", sql_str)


if __name__ == "__main__":
    unittest.main()
