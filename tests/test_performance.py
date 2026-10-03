import pytest
import time
from unittest.mock import AsyncMock, MagicMock
from decimal import Decimal

from src.services.transaction_service import TransactionService
from src.models.category import Category, CategoryType
from src.models.user import User

@pytest.mark.asyncio
async def test_process_voice_performance():
    # Setup mocks
    session = AsyncMock()
    ai_service = AsyncMock()
    category_service = AsyncMock()
    asset_service = AsyncMock()

    # Mock user
    user = User(id=1, family_group_id=None, currency="KZT")
    session.get.side_effect = lambda model, *args: user if model == User else None

    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []
    session.scalars.return_value = mock_scalars

    # Mock available categories
    cat1 = Category(id=1, name="Продукты", type=CategoryType.expense, user_id=None, is_system=True)
    cat2 = Category(id=2, name="Еда вне дома", type=CategoryType.expense, user_id=None, is_system=True)
    cat3 = Category(id=3, name="Зарплата", type=CategoryType.income, user_id=None, is_system=True)
    category_service.get_categories.return_value = [cat1, cat2, cat3]
    category_service.find_by_name.return_value = cat1

    # Mock assets
    asset_service.get_accessible_assets.return_value = []

    # Mock AI response with 500 items to exacerbate the N+1 problem
    items = []
    for i in range(500):
        items.append({
            "amount": 100 + i,
            "item_name": f"item_{i}",
            "type": "expense",
            "category": "Продукты"
        })
    ai_service.parse_voice.return_value = {"items": items}

    service = TransactionService(session=session, ai_service=ai_service)
    service.category_service = category_service
    service.asset_service = asset_service

    # Run the function and measure time
    start_time = time.time()
    transactions = await service.process_voice(1, b"dummy_audio")
    end_time = time.time()

    duration = end_time - start_time
    print(f"\nExecution time: {duration:.4f} seconds")
    print(f"Transactions processed: {len(transactions)}")

    assert len(transactions) == 500
