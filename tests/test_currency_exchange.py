import unittest
from unittest.mock import AsyncMock, MagicMock
from decimal import Decimal
import uuid
import json
from datetime import datetime, timezone

from src.models.user import User
from src.models.category import Category, CategoryType
from src.models.transaction import Transaction, TransactionSource
from src.models.asset import AssetAccount, AssetType
from src.models.family import FamilyGroup
from src.services.ai_service import normalize_receipt_payload
from src.services.transaction_service import TransactionService
from src.services.family_service import FamilyService
from src.bot.messages import BotMessages


class TestCurrencyExchangeAndTransfers(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.user = User(
            id=12345,
            first_name="Aiganym",
            username="aiganym",
            currency="KZT",
            initial_balance=100000.0,
            family_group_id=uuid.uuid4(),
        )

    def test_ai_normalization_sanitizes_currency_purchase(self):
        """Verify legacy 'Покупка валюты' is normalized to 'Денежный перевод'."""
        raw_payload = {
            "is_financial": True,
            "items": [
                {
                    "item_name": "купила 100$ по курсу 450",
                    "amount": 45000.0,
                    "type": "transfer_out",
                    "category": "Покупка валюты",
                    "asset_amount": 100.0,
                    "exchange_rate": 450.0,
                    "target_currency": "USD",
                    "target_asset_name": None,
                }
            ]
        }
        normalized = normalize_receipt_payload(json.dumps(raw_payload))
        item = normalized["items"][0]
        self.assertEqual(item["category"], "Денежный перевод")
        self.assertEqual(item["type"], "transfer_out")
        self.assertEqual(item["exchange_rate"], 450.0)
        self.assertEqual(item["asset_amount"], 100.0)
        self.assertEqual(item["target_currency"], "USD")

    def test_bot_message_dual_ledger_formatting(self):
        """Verify BotMessages.tx_success formats both sides of the conversion."""
        category = Category(id=1, name="Денежный перевод", type=CategoryType.transfer_out)
        asset_acc = AssetAccount(
            id=uuid.uuid4(),
            user_id=self.user.id,
            name="Депозит USD",
            type=AssetType.deposit,
            currency="USD",
            balance=100.0,
        )
        tx = Transaction(
            id=uuid.uuid4(),
            user_id=self.user.id,
            category_id=category.id,
            amount=45000.0,
            type=CategoryType.transfer_out,
            asset_account_id=asset_acc.id,
            asset_amount=100.0,
            exchange_rate=450.0,
            item_name="Пополнение: Депозит USD",
            source=TransactionSource.voice,
        )
        tx.category = category
        tx.asset_account = asset_acc

        msg = BotMessages.tx_success(tx, currency="KZT", current_balance=55000.0)

        # Assert dual ledger presentation
        self.assertIn("Списано:", msg)
        self.assertIn("-45 000", msg)
        self.assertIn("Зачислено:", msg)
        self.assertIn("+100", msg)
        self.assertIn("Курс:", msg)
        self.assertIn("1 $ = 450", msg)
        self.assertIn("Депозит USD", msg)
        self.assertIn("Денежный перевод", msg)
        self.assertIn("Общий капитал не изменился (конвертация)", msg)
        self.assertIn("55 000", msg)

    async def test_transaction_service_auto_scales_and_resolves_asset(self):
        """Verify TransactionService auto-scales base currency amount if needed and links asset."""
        session = AsyncMock()
        service = TransactionService(session=session)

        # Mock dependencies
        service.ai_service = MagicMock()
        service.asset_service = MagicMock()
        service.credit_service = MagicMock()
        service.credit_service.get_user_credits = AsyncMock(return_value=[])
        service.category_service = MagicMock()
        service.dynamic_service = MagicMock()
        service.dynamic_service.get_few_shots_for_query = AsyncMock(return_value=[])
        service.dynamic_service.format_few_shots_prompt = MagicMock(return_value="")

        # Mock voice response
        service.ai_service.parse_voice = AsyncMock(return_value={
            "is_financial": True,
            "items": [
                {
                    "item_name": "купила 100$ по курсу 450 тенге",
                    "amount": 100.0,  # AI returned foreign amount mistakenly as base amount
                    "type": "transfer_out",
                    "category": "Денежный перевод",
                    "asset_amount": 100.0,
                    "exchange_rate": 450.0,
                    "target_currency": "USD",
                    "target_asset_name": None,
                }
            ]
        })

        cat = Category(id=10, name="Денежный перевод", type=CategoryType.transfer_out)

        async def mock_get(model, pk):
            if model == User:
                return self.user
            if model == Category:
                return cat
            return None
        session.get = AsyncMock(side_effect=mock_get)
        session.scalar = AsyncMock(return_value=None)

        target_asset = AssetAccount(
            id=uuid.uuid4(),
            user_id=self.user.id,
            name="Депозит USD",
            type=AssetType.deposit,
            currency="USD",
            balance=100.0,
        )
        service.asset_service.resolve_asset_account = AsyncMock(return_value=target_asset)
        service.asset_service.get_accessible_assets = AsyncMock(return_value=[target_asset])

        # Mock category service
        service.category_service.get_categories = AsyncMock(return_value=[cat])
        service.category_service.find_by_name = AsyncMock(return_value=cat)

        # Mock category resolution
        session.scalars = MagicMock()
        mock_result = MagicMock()
        mock_result.all.return_value = [cat]
        session.scalars.return_value = mock_result

        txs = await service.process_voice(
            user_id=self.user.id,
            audio_bytes=b"dummy_bytes",
        )

        self.assertEqual(len(txs), 1)
        tx = txs[0]
        # Auto-scaled to 45 000 KZT
        self.assertEqual(tx.amount, 45000.0)
        self.assertEqual(tx.asset_amount, 100.0)
        self.assertEqual(tx.exchange_rate, 450.0)
        self.assertEqual(tx.type, CategoryType.transfer_out)
        self.assertEqual(tx.item_name, "Покупка валюты")
        self.assertEqual(tx.asset_account.name, "Депозит USD")

    async def test_family_joint_feed_exposes_asset_amount_and_currency(self):
        """Verify FamilyService.get_family_transactions exposes asset transfer details."""
        session = AsyncMock()
        family_service = FamilyService(session=session)

        group = FamilyGroup(
            id=self.user.family_group_id,
            name="Семья",
            owner_id=self.user.id,
            invite_code="XYZ123",
        )
        family_service.get_or_create_user_family = AsyncMock(return_value=group)

        # Mock member IDs query
        scalars_mock_members = MagicMock()
        scalars_mock_members.all.return_value = [self.user.id]

        # Mock transactions query
        category = Category(id=1, name="Денежный перевод", type=CategoryType.transfer_out)
        asset_acc = AssetAccount(
            id=uuid.uuid4(),
            user_id=self.user.id,
            name="Депозит USD",
            currency="USD",
            balance=100.0,
        )
        tx = Transaction(
            id=uuid.uuid4(),
            user_id=self.user.id,
            category_id=category.id,
            amount=45000.0,
            type=CategoryType.transfer_out,
            asset_account_id=asset_acc.id,
            asset_amount=100.0,
            exchange_rate=450.0,
            item_name="Пополнение: Депозит USD",
            source=TransactionSource.voice,
            transaction_date=datetime.now(timezone.utc),
        )
        tx.category = category
        tx.user = self.user
        tx.asset_account = asset_acc

        scalars_mock_txs = MagicMock()
        unique_mock = MagicMock()
        unique_mock.all.return_value = [tx]
        scalars_mock_txs.unique.return_value = unique_mock

        session.scalars.side_effect = [scalars_mock_members, scalars_mock_txs]

        items = await family_service.get_family_transactions(user=self.user)

        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item["amount"], 45000.0)
        self.assertEqual(item["asset_amount"], 100.0)
        self.assertEqual(item["exchange_rate"], 450.0)
        self.assertEqual(item["asset_currency"], "USD")
        self.assertEqual(item["type"], "transfer_out")
        self.assertEqual(item["category_name"], "Денежный перевод")


if __name__ == "__main__":
    unittest.main()
