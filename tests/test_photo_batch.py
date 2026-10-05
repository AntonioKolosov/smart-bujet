import unittest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession
from src.bot.handlers.photo_tx import MediaGroupBuffer, process_photo_transaction, media_group_buffer
from src.services.transaction_service import TransactionService
from src.services.ai_service import AIService
from src.models.user import User
from src.models.category import Category, CategoryType
from src.models.transaction import Transaction
from src.core.exceptions import OffTopicMessageError, TransactionParseError, InvalidTransactionAmountError
from src.bot.messages import BotMessages


class TestMediaGroupBuffer(unittest.IsolatedAsyncioTestCase):
    async def test_leader_and_followers_coordination(self):
        buffer = MediaGroupBuffer(debounce_delay=0.05, max_wait=0.2)
        mg_id = "test_mg_1"

        msg1 = MagicMock()
        msg1.message_id = 101
        msg2 = MagicMock()
        msg2.message_id = 102
        msg3 = MagicMock()
        msg3.message_id = 103

        async def send_msg(msg, delay=0.0):
            if delay > 0:
                await asyncio.sleep(delay)
            return await buffer.add_and_wait(mg_id, msg)

        # M1 arrives at 0, M2 at 0.01s, M3 at 0.02s
        res1, res2, res3 = await asyncio.gather(
            send_msg(msg1, 0.0),
            send_msg(msg2, 0.01),
            send_msg(msg3, 0.02)
        )

        # res1 should be the leader and get all 3 messages
        self.assertIsNotNone(res1)
        self.assertEqual(len(res1), 3)
        self.assertEqual([m.message_id for m in res1], [101, 102, 103])

        # res2 and res3 must be followers and get None
        self.assertIsNone(res2)
        self.assertIsNone(res3)

    async def test_independent_media_groups(self):
        buffer = MediaGroupBuffer(debounce_delay=0.05, max_wait=0.2)

        msg_a1 = MagicMock()
        msg_a1.message_id = 1
        msg_b1 = MagicMock()
        msg_b1.message_id = 2

        res_a, res_b = await asyncio.gather(
            buffer.add_and_wait("group_a", msg_a1),
            buffer.add_and_wait("group_b", msg_b1),
        )

        self.assertIsNotNone(res_a)
        self.assertEqual(len(res_a), 1)
        self.assertEqual(res_a[0].message_id, 1)

        self.assertIsNotNone(res_b)
        self.assertEqual(len(res_b), 1)
        self.assertEqual(res_b[0].message_id, 2)


class TestAIServiceBatch(unittest.IsolatedAsyncioTestCase):
    async def test_parse_receipt_photos_concurrent(self):
        ai_service = AIService(api_key=None)
        ai_service.parse_receipt_photo = AsyncMock(side_effect=[
            {"is_financial": True, "items": [{"item_name": "Хлеб", "amount": 200, "category": "Продукты"}]},
            {"is_financial": True, "items": [{"item_name": "Молоко", "amount": 450, "category": "Продукты"}]},
        ])

        results = await ai_service.parse_receipt_photos(
            images=[b"img1", b"img2"],
            mime_type="image/jpeg",
            categories=["Продукты"]
        )

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["items"][0]["item_name"], "Хлеб")
        self.assertEqual(results[1]["items"][0]["item_name"], "Молоко")
        self.assertEqual(ai_service.parse_receipt_photo.call_count, 2)

    async def test_parse_receipt_photos_empty(self):
        ai_service = AIService(api_key=None)
        results = await ai_service.parse_receipt_photos([], "image/jpeg", ["Продукты"])
        self.assertEqual(results, [])


class TestTransactionServiceBatch(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.session = AsyncMock(spec=AsyncSession)
        self.user = MagicMock(spec=User)
        self.user.id = 42
        self.user.family_group_id = None
        self.user.currency = "KZT"

        async def mock_get(model, id):
            if model == User:
                return self.user
            return None
        self.session.get = AsyncMock(side_effect=mock_get)

        self.cat_food = Category(id=1, name="Продукты", type=CategoryType.expense)
        self.cat_dining = Category(id=2, name="Еда вне дома", type=CategoryType.expense)

    async def test_process_receipt_photos_multiple_successful(self):
        ai_mock = AsyncMock()
        # Photo 1: Retail receipt (Magnum) with 2 items
        # Photo 2: Dining receipt (Coffee Boom) with dining aggregation
        ai_mock.parse_receipt_photo.side_effect = [
            {
                "is_financial": True,
                "venue_name": "Magnum",
                "items": [
                    {"item_name": "Хлеб", "amount": 250, "category": "Продукты", "type": "expense"},
                    {"item_name": "Сыр", "amount": 1500, "category": "Продукты", "type": "expense"},
                ],
                "discount_percent": None,
                "discount_amount": None,
                "total_paid": 1750
            },
            {
                "is_financial": True,
                "establishment_type": "dining",
                "venue_name": "Coffee Boom",
                "items": [
                    {"item_name": "Капучино", "amount": 1200, "category": "Еда вне дома", "type": "expense"},
                    {"item_name": "Круассан", "amount": 800, "category": "Еда вне дома", "type": "expense"},
                ],
                "discount_percent": None,
                "discount_amount": None,
                "total_paid": 2000
            }
        ]

        tx_service = TransactionService(session=self.session, ai_service=ai_mock)
        tx_service.category_service.get_categories = AsyncMock(return_value=[self.cat_food, self.cat_dining])
        tx_service.category_service.find_by_name = AsyncMock(side_effect=lambda name, cat_type, uid: (
            self.cat_dining if name == "Еда вне дома" else self.cat_food
        ))
        tx_service._save_alias = AsyncMock(return_value=None)
        tx_service._get_alias_category = AsyncMock(return_value=None)

        res = await tx_service.process_receipt_photos(
            user_id=42,
            images=[b"photo1", b"photo2"]
        )

        self.assertEqual(res["processed_count"], 2)
        self.assertEqual(res["failed_count"], 0)
        self.assertEqual(res["total_amount"], 3750.0)  # 1750 + 2000
        self.assertEqual(res["total_operations"], 3)   # 2 items from Magnum, 1 aggregated from Coffee Boom
        self.assertEqual(len(res["receipts"]), 2)

        # Receipt 1 check
        r1 = res["receipts"][0]
        self.assertEqual(r1["title"], "Magnum")
        self.assertEqual(r1["total_amount"], 1750.0)
        self.assertEqual(r1["items_count"], 2)

        # Receipt 2 check (Dining aggregated to 1 item)
        r2 = res["receipts"][1]
        self.assertEqual(r2["title"], "Coffee Boom")
        self.assertEqual(r2["total_amount"], 2000.0)
        self.assertEqual(r2["items_count"], 1)

        # Single atomic commit
        self.assertTrue(self.session.commit.called)
        self.assertEqual(self.session.commit.call_count, 1)

    async def test_process_receipt_photos_partial_resilience(self):
        """When 1 of 2 photos is off-topic (e.g. meme), the valid receipt is still processed successfully."""
        ai_mock = AsyncMock()
        ai_mock.parse_receipt_photo.side_effect = [
            {"is_financial": False, "items": []},  # Photo 1 is a meme
            {
                "is_financial": True,
                "venue_name": "Аптека",
                "items": [{"item_name": "Витамины", "amount": 3200, "category": "Продукты", "type": "expense"}],
                "discount_percent": None,
                "discount_amount": None,
                "total_paid": 3200
            }
        ]

        tx_service = TransactionService(session=self.session, ai_service=ai_mock)
        tx_service.category_service.get_categories = AsyncMock(return_value=[self.cat_food])
        tx_service.category_service.find_by_name = AsyncMock(return_value=self.cat_food)
        tx_service._save_alias = AsyncMock(return_value=None)
        tx_service._get_alias_category = AsyncMock(return_value=None)

        res = await tx_service.process_receipt_photos(
            user_id=42,
            images=[b"meme_photo", b"receipt_photo"]
        )

        self.assertEqual(res["processed_count"], 1)
        self.assertEqual(res["failed_count"], 1)
        self.assertEqual(res["total_amount"], 3200.0)
        self.assertEqual(res["total_operations"], 1)
        self.assertTrue(self.session.commit.called)

    async def test_process_receipt_photos_all_off_topic_raises_error(self):
        """When all photos in the album are non-financial, raise OffTopicMessageError."""
        ai_mock = AsyncMock()
        ai_mock.parse_receipt_photo.return_value = {"is_financial": False, "items": []}

        tx_service = TransactionService(session=self.session, ai_service=ai_mock)
        tx_service.category_service.get_categories = AsyncMock(return_value=[self.cat_food])

        with self.assertRaises(OffTopicMessageError):
            await tx_service.process_receipt_photos(user_id=42, images=[b"p1", b"p2"])

    async def test_single_photo_flow_unchanged(self):
        """Verify process_receipt_photo works exactly as before."""
        ai_mock = AsyncMock()
        ai_mock.parse_receipt_photo.return_value = {
            "is_financial": True,
            "items": [{"item_name": "Чай", "amount": 500, "category": "Продукты", "type": "expense"}],
            "discount_percent": None,
            "discount_amount": None,
            "total_paid": 500
        }

        tx_service = TransactionService(session=self.session, ai_service=ai_mock)
        tx_service.category_service.get_categories = AsyncMock(return_value=[self.cat_food])
        tx_service.category_service.find_by_name = AsyncMock(return_value=self.cat_food)
        tx_service._save_alias = AsyncMock(return_value=None)
        tx_service._get_alias_category = AsyncMock(return_value=None)

        txs = await tx_service.process_receipt_photo(user_id=42, image_bytes=b"single_img")
        self.assertEqual(len(txs), 1)
        self.assertEqual(txs[0].amount, 500.0)
        self.assertEqual(txs[0].item_name, "Чай")
        self.assertTrue(self.session.commit.called)


class TestBotMessagesBatch(unittest.TestCase):
    def test_receipt_batch_success_formatting(self):
        receipts = [
            {"title": "Magnum", "total_amount": 15000.0, "items_count": 3},
            {"title": "Кафе Del Papa", "total_amount": 4500.0, "items_count": 1},
            {"title": "Чек", "total_amount": 2100.0, "items_count": 2},
        ]
        msg = BotMessages.receipt_batch_success(
            receipts=receipts,
            total_operations=6,
            total_amount=21600.0,
            currency="KZT",
            current_balance=125000.0
        )

        self.assertIn("Обработано чеков: 3", msg)
        self.assertIn("Чек 1: <b>Magnum</b> (15 000.00 ₸)", msg)
        self.assertIn("Чек 2: <b>Кафе Del Papa</b> (4 500.00 ₸)", msg)
        self.assertIn("Чек 3 (2 100.00 ₸)", msg)
        self.assertIn("Всего добавлено операций: 6 на сумму: 21 600.00 ₸", msg)
        self.assertIn("Текущий баланс: 125 000.00 ₸", msg)


class TestPhotoHandlerIntegration(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.session = AsyncMock(spec=AsyncSession)
        self.user = User(
            id=123,
            username="testuser",
            first_name="Test",
            currency="KZT",
            initial_balance=100000.0
        )
        self.session.get = AsyncMock(return_value=self.user)
        self.bot = AsyncMock()
        async def mock_download(file_id, destination):
            destination.write(b"fake_image_bytes")
        self.bot.download = AsyncMock(side_effect=mock_download)

    async def test_single_photo_handler_flow(self):
        message = MagicMock()
        message.from_user.id = 123
        message.from_user.username = "testuser"
        message.from_user.first_name = "Test"
        message.chat.id = 123
        message.media_group_id = None
        photo_size = MagicMock()
        photo_size.file_id = "single_file_id"
        message.photo = [photo_size]
        message.reply = AsyncMock()

        dummy_tx = MagicMock(spec=Transaction)
        dummy_tx.id = 1
        dummy_tx.amount = 500.0
        dummy_tx.type = CategoryType.expense
        dummy_tx.item_name = "Кофе"
        dummy_tx.category = MagicMock(name="Кафе")
        dummy_tx.discount_amount = None
        dummy_tx.asset_amount = None

        with patch("src.bot.handlers.photo_tx.TransactionService") as MockTxService:
            instance = MockTxService.return_value
            instance.process_receipt_photo = AsyncMock(return_value=[dummy_tx])
            instance.get_user_balance = AsyncMock(return_value={"current_balance": 99500.0})

            await process_photo_transaction(message, self.session, self.bot)

            # Verified process_receipt_photo was called for single photo
            instance.process_receipt_photo.assert_called_once()
            message.reply.assert_called_once()
            reply_text = message.reply.call_args[0][0]
            self.assertIn("Записано", reply_text)

    async def test_media_group_album_handler_flow(self):
        mg_id = "test_album_99"

        # Create 2 messages with same media_group_id
        m1 = MagicMock()
        m1.from_user.id = 123
        m1.chat.id = 123
        m1.media_group_id = mg_id
        p1 = MagicMock()
        p1.file_id = "file_1"
        m1.photo = [p1]
        m1.reply = AsyncMock()

        m2 = MagicMock()
        m2.from_user.id = 123
        m2.chat.id = 123
        m2.media_group_id = mg_id
        p2 = MagicMock()
        p2.file_id = "file_2"
        m2.photo = [p2]
        m2.reply = AsyncMock()

        dummy_tx1 = MagicMock(spec=Transaction)
        dummy_tx1.id = 10
        dummy_tx1.amount = 1500.0
        dummy_tx1.type = CategoryType.expense

        dummy_tx2 = MagicMock(spec=Transaction)
        dummy_tx2.id = 11
        dummy_tx2.amount = 3000.0
        dummy_tx2.type = CategoryType.expense

        batch_result = {
            "receipts": [
                {"title": "Magnum", "total_amount": 1500.0, "items_count": 1, "transactions": [dummy_tx1]},
                {"title": "Кафе", "total_amount": 3000.0, "items_count": 1, "transactions": [dummy_tx2]},
            ],
            "all_transactions": [dummy_tx1, dummy_tx2],
            "total_amount": 4500.0,
            "total_operations": 2,
            "processed_count": 2,
            "failed_count": 0
        }

        with patch("src.bot.handlers.photo_tx.TransactionService") as MockTxService, \
             patch.object(media_group_buffer, "debounce_delay", 0.05), \
             patch.object(media_group_buffer, "max_wait", 0.2):

            instance = MockTxService.return_value
            instance.process_receipt_photos = AsyncMock(return_value=batch_result)
            instance.get_user_balance = AsyncMock(return_value={"current_balance": 95500.0})

            # Simulate concurrent dispatch from aiogram
            await asyncio.gather(
                process_photo_transaction(m1, self.session, self.bot),
                process_photo_transaction(m2, self.session, self.bot)
            )

            # process_receipt_photos must be called ONCE with both images
            instance.process_receipt_photos.assert_called_once()
            call_images = instance.process_receipt_photos.call_args[1]["images"]
            self.assertEqual(len(call_images), 2)

            # Only ONE reply should be sent (from leader m1), m2 must not reply
            m1.reply.assert_called_once()
            m2.reply.assert_not_called()

            consolidated_text = m1.reply.call_args[0][0]
            self.assertIn("Обработано чеков: 2", consolidated_text)
            self.assertIn("Magnum", consolidated_text)
            self.assertIn("Кафе", consolidated_text)
            self.assertIn("Всего добавлено операций: 2 на сумму: 4 500.00 ₸", consolidated_text)
            self.assertIn("Текущий баланс: 95 500.00 ₸", consolidated_text)


if __name__ == "__main__":
    unittest.main()
