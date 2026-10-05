import unittest
from unittest.mock import AsyncMock, MagicMock
from decimal import Decimal

try:
    from src.core.exceptions import OffTopicMessageError
    from src.services.ai_service import normalize_receipt_payload
    from src.bot.messages import BotMessages
    from sqlalchemy.ext.asyncio import AsyncSession
    from src.services.transaction_service import TransactionService
    from src.models.user import User
    from src.models.category import Category, CategoryType
    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False


class TestGuardrailsPayloadNormalization(unittest.TestCase):
    def setUp(self):
        if not HAS_DEPS:
            self.skipTest("Dependencies not available in current environment")

    def test_normalize_payload_rejects_off_topic(self):
        raw_json = '{"is_financial": false, "items": []}'
        payload = normalize_receipt_payload(raw_json)
        self.assertFalse(payload.get("is_financial"))
        self.assertEqual(payload.get("items"), [])

    def test_normalize_payload_accepts_financial(self):
        raw_json = '{"is_financial": true, "items": [{"item_name": "Кофе", "amount": 250, "category": "Кафе", "type": "expense"}]}'
        payload = normalize_receipt_payload(raw_json)
        self.assertTrue(payload.get("is_financial"))
        self.assertEqual(len(payload.get("items", [])), 1)

    def test_normalize_payload_markdown_wrapped_off_topic(self):
        raw_json = '```json\n{"is_financial": false, "items": []}\n```'
        payload = normalize_receipt_payload(raw_json)
        self.assertFalse(payload.get("is_financial"))
        self.assertEqual(payload.get("items"), [])


class TestGuardrailsTransactionService(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        if not HAS_DEPS:
            self.skipTest("Dependencies not available in current environment")

        self.session_mock = AsyncMock(spec=AsyncSession)
        self.user_mock = MagicMock(spec=User)
        self.user_mock.id = 123
        self.user_mock.family_group_id = None
        self.user_mock.currency = "KZT"

        async def mock_get(model, id):
            if model == User:
                return self.user_mock
            return None
        self.session_mock.get = AsyncMock(side_effect=mock_get)

    async def test_process_text_off_topic_raises_guardrail_error(self):
        ai_mock = AsyncMock()
        ai_mock.classify_text.return_value = {
            "is_financial": False,
            "items": []
        }

        service = TransactionService(session=self.session_mock, ai_service=ai_mock)
        service.category_service.get_categories = AsyncMock(return_value=[])
        service.asset_service.get_accessible_assets = AsyncMock(return_value=[])
        service.credit_service.get_user_credits = AsyncMock(return_value=[])
        service.dynamic_service.get_few_shots_for_query = AsyncMock(return_value=[])

        with self.assertRaises(OffTopicMessageError):
            await service.process_text(user_id=123, text="Какая сегодня погода в Алматы?")

    async def test_process_voice_off_topic_raises_guardrail_error(self):
        ai_mock = AsyncMock()
        ai_mock.parse_voice.return_value = {
            "is_financial": False,
            "items": []
        }

        service = TransactionService(session=self.session_mock, ai_service=ai_mock)
        service.category_service.get_categories = AsyncMock(return_value=[])
        service.asset_service.get_accessible_assets = AsyncMock(return_value=[])
        service.credit_service.get_user_credits = AsyncMock(return_value=[])
        service.dynamic_service.get_few_shots_for_query = AsyncMock(return_value=[])

        with self.assertRaises(OffTopicMessageError):
            await service.process_voice(user_id=123, audio_bytes=b"dummy_ogg_audio")

    async def test_process_receipt_photo_off_topic_raises_guardrail_error(self):
        ai_mock = AsyncMock()
        ai_mock.parse_receipt_photo.return_value = {
            "is_financial": False,
            "items": []
        }

        service = TransactionService(session=self.session_mock, ai_service=ai_mock)
        service.category_service.get_categories = AsyncMock(return_value=[])

        with self.assertRaises(OffTopicMessageError):
            await service.process_receipt_photo(user_id=123, image_bytes=b"dummy_jpeg_image")


class TestGuardrailsBotMessages(unittest.TestCase):
    def setUp(self):
        if not HAS_DEPS:
            self.skipTest("Dependencies not available in current environment")

    def test_off_topic_warnings(self):
        text_warning = BotMessages.off_topic_warning("text")
        self.assertIn("Smart Bujet", text_warning)
        self.assertIn("финансовый ассистент", text_warning)

        voice_warning = BotMessages.off_topic_warning("voice")
        self.assertIn("голосовом", voice_warning.lower())

        photo_warning = BotMessages.off_topic_warning("photo")
        self.assertIn("фотографии", photo_warning.lower())
        self.assertIn("чек", photo_warning.lower())


if __name__ == "__main__":
    unittest.main()
