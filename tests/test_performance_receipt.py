import unittest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock
from decimal import Decimal

try:
    from sqlalchemy.ext.asyncio import AsyncSession
    from src.services.transaction_service import TransactionService
    from src.models.user import User
    from src.models.category import Category, CategoryType
    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False


class TestPerformanceReceiptAndVoice(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        if not HAS_DEPS:
            self.skipTest("SQLAlchemy or project dependencies not installed in current environment")

    async def test_process_receipt_photo_performance(self):
        session_mock = AsyncMock(spec=AsyncSession)
        user_mock = MagicMock(spec=User)
        user_mock.family_group_id = None
        user_mock.currency = "KZT"

        async def mock_get(model, id):
            if model == User:
                return user_mock
            return None
        session_mock.get = AsyncMock(side_effect=mock_get)

        category_mock = Category(
            id=1,
            name="Продукты",
            type=CategoryType.expense,
            is_system=True
        )

        ai_service_mock = AsyncMock()

        items_same = []
        for i in range(1000):
            items_same.append({
                "amount": 100 + i,
                "item_name": "Apple",
                "type": "expense",
                "category": "Продукты"
            })

        ai_service_mock.parse_receipt_photo.return_value = {
            "items": items_same,
            "discount_percent": None,
            "discount_amount": None,
            "total_paid": None
        }

        transaction_service = TransactionService(session=session_mock, ai_service=ai_service_mock)

        async def mock_get_categories(*args, **kwargs):
            await asyncio.sleep(0.001)
            return [category_mock]

        async def mock_find_by_name(*args, **kwargs):
            await asyncio.sleep(0.001)

        transaction_service.category_service.get_categories = AsyncMock(side_effect=mock_get_categories)
        transaction_service.category_service.find_by_name = AsyncMock(side_effect=mock_find_by_name)

        save_alias_call_count = 0
        async def mock_save_alias(*args, **kwargs):
            nonlocal save_alias_call_count
            save_alias_call_count += 1
            await asyncio.sleep(0.001)
        transaction_service._save_alias = AsyncMock(side_effect=mock_save_alias)

        async def mock_get_alias_category(*args, **kwargs):
            await asyncio.sleep(0.001)

        async def mock_resolve_category(*args, **kwargs):
            await asyncio.sleep(0.001)
            return category_mock

        transaction_service._get_alias_category = AsyncMock(side_effect=mock_get_alias_category)
        transaction_service._resolve_category = AsyncMock(side_effect=mock_resolve_category)

        start = time.perf_counter()
        await transaction_service.process_receipt_photo(user_id=1, image_bytes=b"dummy")
        end = time.perf_counter()

        duration = end - start
        # Without cache this would take > 2-3 seconds for 1000 items
        self.assertLess(duration, 1.0, f"Performance issue: took {duration}s to process cached items")
        # Ensure write deduplication: save_alias should only be called once for identical normalized names
        self.assertEqual(save_alias_call_count, 1, "Save alias must be deduplicated across batch")

    async def test_process_voice_performance(self):
        session_mock = AsyncMock(spec=AsyncSession)
        user_mock = MagicMock(spec=User)
        user_mock.family_group_id = None
        user_mock.currency = "KZT"

        async def mock_get(model, id):
            if model == User:
                return user_mock
            return None
        session_mock.get = AsyncMock(side_effect=mock_get)

        category_mock = Category(
            id=1,
            name="Продукты",
            type=CategoryType.expense,
            is_system=True
        )

        ai_service_mock = AsyncMock()

        items_same = []
        for i in range(100):
            items_same.append({
                "amount": 100 + i,
                "item_name": "Хлеб",
                "raw_text": "купил хлеб",
                "type": "expense",
                "category": "Продукты"
            })

        ai_service_mock.parse_voice.return_value = {
            "items": items_same,
            "discount_percent": None,
            "discount_amount": None,
            "total_paid": None
        }

        transaction_service = TransactionService(session=session_mock, ai_service=ai_service_mock)

        async def mock_get_categories(*args, **kwargs):
            await asyncio.sleep(0.001)
            return [category_mock]

        transaction_service.category_service.get_categories = AsyncMock(side_effect=mock_get_categories)
        transaction_service.asset_service.get_accessible_assets = AsyncMock(return_value=[])
        transaction_service.credit_service.get_user_credits = AsyncMock(return_value=[])
        transaction_service.dynamic_service.get_few_shots_for_query = AsyncMock(return_value=[])
        transaction_service._save_alias = AsyncMock(return_value=None)
        transaction_service._get_alias_category = AsyncMock(return_value=None)
        transaction_service._resolve_category = AsyncMock(return_value=category_mock)

        start = time.perf_counter()
        await transaction_service.process_voice(user_id=1, audio_bytes=b"dummy")
        end = time.perf_counter()

        duration = end - start
        self.assertLess(duration, 0.5, f"Voice performance issue: took {duration}s")


if __name__ == "__main__":
    unittest.main()
