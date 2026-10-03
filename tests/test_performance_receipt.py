import pytest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock
from src.services.transaction_service import TransactionService
from src.models.user import User
from src.models.category import Category, CategoryType
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

@pytest.mark.asyncio
async def test_process_receipt_photo_performance():
    # Setup mock session
    session_mock = AsyncMock(spec=AsyncSession)
    user_mock = MagicMock(spec=User)
    user_mock.family_group_id = None
    user_mock.currency = "KZT"

    # We need to distinguish session.get for User vs Category
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

    # Generate 1000 items with same name, and 1000 items with different names
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
        return None

    transaction_service.category_service.get_categories = AsyncMock(side_effect=mock_get_categories)
    transaction_service.category_service.find_by_name = AsyncMock(side_effect=mock_find_by_name)

    async def mock_save_alias(*args, **kwargs):
        return None
    transaction_service._save_alias = AsyncMock(side_effect=mock_save_alias)

    async def mock_get_alias_category(*args, **kwargs):
        await asyncio.sleep(0.001)
        return None

    async def mock_resolve_category(*args, **kwargs):
        await asyncio.sleep(0.001)
        return category_mock

    transaction_service._get_alias_category = AsyncMock(side_effect=mock_get_alias_category)
    transaction_service._resolve_category = AsyncMock(side_effect=mock_resolve_category)

    start = time.perf_counter()
    await transaction_service.process_receipt_photo(user_id=1, image_bytes=b"dummy")
    end = time.perf_counter()

    duration = end - start
    print(f"\nProcessing 1000 identical items took {duration:.4f} seconds")

    # Assert performance threshold: without cache this would take > 2 seconds
    assert duration < 1.0, f"Performance issue: took {duration}s to process cached items"
