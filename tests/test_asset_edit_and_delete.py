import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import uuid
from decimal import Decimal

from src.models.user import User
from src.models.asset import AssetAccount, AssetType
from src.models.transaction import Transaction
from src.models.category import CategoryType
from src.services.asset_service import AssetService


class TestAssetEditAndDelete(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.session = AsyncMock()
        self.service = AssetService(self.session)
        self.user = User(id=123, first_name="Aiganym")
        self.asset = AssetAccount(
            id=uuid.uuid4(),
            user_id=self.user.id,
            name="Депозит Kaspi",
            type=AssetType.deposit,
            currency="KZT",
            balance=100000.0,
            interest_rate=14.0,
            is_active=True
        )

    async def test_update_asset_success(self):
        self.session.scalar = AsyncMock(return_value=self.asset)

        updated = await self.service.update_asset(
            user_id=self.user.id,
            asset_id=self.asset.id,
            name="Новый Kaspi",
            asset_type=AssetType.savings,
            currency="USD",
            balance=250.0,
            interest_rate=2.5
        )

        self.assertIsNotNone(updated)
        self.assertEqual(updated.name, "Новый Kaspi")
        self.assertEqual(updated.type, AssetType.savings)
        self.assertEqual(updated.currency, "USD")
        self.assertEqual(updated.balance, 250.0)
        self.assertEqual(updated.interest_rate, 2.5)
        self.session.commit.assert_called_once()

    async def test_update_asset_not_found(self):
        self.session.scalar = AsyncMock(return_value=None)

        res = await self.service.update_asset(
            user_id=self.user.id,
            asset_id=uuid.uuid4(),
            name="Тест"
        )

        self.assertIsNone(res)
        self.session.commit.assert_not_called()

    async def test_delete_asset_cleans_up_transactions_and_deletes_account(self):
        self.session.scalar = AsyncMock(return_value=self.asset)

        success = await self.service.delete_asset(
            user_id=self.user.id,
            asset_id=self.asset.id
        )

        self.assertTrue(success)
        # Verify queries were executed:
        # 1. delete accrued interest
        # 2. update to detach transfers
        self.assertEqual(self.session.execute.call_count, 2)
        # Verify asset was deleted
        self.session.delete.assert_called_once_with(self.asset)
        self.session.commit.assert_called_once()

    async def test_delete_asset_not_found(self):
        self.session.scalar = AsyncMock(return_value=None)

        success = await self.service.delete_asset(
            user_id=self.user.id,
            asset_id=uuid.uuid4()
        )

        self.assertFalse(success)
        self.session.delete.assert_not_called()


if __name__ == "__main__":
    unittest.main()
