from decimal import Decimal
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

from src.bot.handlers.tx_actions import handle_tx_toggle
from src.core.security import blind_index, decrypt_value, encrypt_value
from src.models.alias import UserItemAlias
from src.models.category import Category, CategoryType
from src.models.transaction import Transaction
from src.models.user import User
from src.services.ai_service import AIService, _ADVICE_CACHE, _build_gen_config
from src.services.dynamic_context_service import DynamicContextService
from src.services.parser_service import ParserService
from src.services.transaction_service import TransactionService


class TestAILatencyOptimizations(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        _ADVICE_CACHE.clear()

    def test_gen_config_disables_thinking_and_afc(self):
        cfg = _build_gen_config(temperature=0.1, max_output_tokens=4096)
        if cfg is not None:
            self.assertEqual(cfg.max_output_tokens, 4096)
            if getattr(cfg, "thinking_config", None) is not None:
                self.assertEqual(cfg.thinking_config.thinking_budget, 0)
            if getattr(cfg, "automatic_function_calling", None) is not None:
                self.assertTrue(cfg.automatic_function_calling.disable)

    async def test_shared_genai_client_singleton_and_custom_override(self):
        with patch("src.services.ai_service.genai") as mock_genai:
            mock_genai.Client.side_effect = lambda api_key: MagicMock(api_key=api_key)
            s1 = AIService(api_key="live-key-1")
            s2 = AIService(api_key="live-key-1")
            c1 = s1.client
            c2 = s2.client
            self.assertIs(c1, c2)
            self.assertEqual(mock_genai.Client.call_count, 1)

            custom = MagicMock()
            s2.client = custom
            self.assertIs(s2.client, custom)

    def test_cached_aesgcm_encrypt_decrypt_and_blind_index(self):
        ct = encrypt_value("Магнум продукты")
        self.assertTrue(ct.startswith("enc:v1:"))
        self.assertEqual(decrypt_value(ct), "Магнум продукты")
        h1 = blind_index("Магнум")
        h2 = blind_index("  магнум ")
        self.assertEqual(h1, h2)
        self.assertEqual(len(h1), 64)

    def test_parser_space_thousands_and_safety_bypasses(self):
        self.assertEqual(
            ParserService.parse_text("продукты 15 000"),
            (Decimal("15000"), "Продукты"),
        )
        self.assertEqual(
            ParserService.parse_text("1 250 000 тг магнум"),
            (Decimal("1250000"), "Магнум"),
        )
        # Multi-item must still bypass to AI
        self.assertIsNone(ParserService.parse_text("хлеб 300 молоко 600"))
        # Family transfer & questions must bypass to AI
        self.assertIsNone(ParserService.parse_text("мужу 15 000"))
        self.assertIsNone(ParserService.parse_text("сколько стоит молоко 500?"))

    def test_parser_deterministic_category_guesser(self):
        self.assertEqual(ParserService.guess_category("Магнум"), "Продукты")
        self.assertEqual(ParserService.guess_category("Манты"), "Продукты")
        self.assertEqual(ParserService.guess_category("Кофейня Старбакс"), "Еда вне дома")
        self.assertEqual(ParserService.guess_category("Яндекс такси"), "Транспорт")
        self.assertEqual(ParserService.guess_category("Аптека витамины"), "Здоровье")
        self.assertIsNone(ParserService.guess_category("Непонятная штука"))

    async def test_process_text_deterministic_fast_path_skips_gemini(self):
        session = AsyncMock()
        ai_mock = AsyncMock()
        tx_service = TransactionService(session=session, ai_service=ai_mock)

        user = User(id=101, first_name="Антон", currency="KZT", initial_balance=50000.0)
        food_cat = Category(id=1, name="Продукты", type=CategoryType.expense, is_system=True)

        session.get = AsyncMock(return_value=user)
        tx_service._get_alias_category = AsyncMock(return_value=None)
        tx_service.category_service.find_by_name = AsyncMock(return_value=food_cat)
        tx_service._save_alias = AsyncMock()
        session.add = MagicMock()
        session.commit = AsyncMock()

        txs = await tx_service.process_text(user_id=101, text="магнум 15 000")

        self.assertEqual(len(txs), 1)
        self.assertEqual(txs[0].amount, 15000.0)
        self.assertEqual(txs[0].item_name, "Магнум")
        self.assertEqual(txs[0].category.name, "Продукты")
        ai_mock.classify_text.assert_not_called()

    async def test_tx_toggle_writes_blind_index_hash_not_plaintext(self):
        session = AsyncMock()
        tx_id = uuid.uuid4()
        old_cat = Category(id=1, name="Прочее", type=CategoryType.expense, is_system=True)
        new_cat = Category(id=2, name="Зарплата", type=CategoryType.income, is_system=True)
        tx = Transaction(
            id=tx_id,
            user_id=555,
            category_id=1,
            amount=20000.0,
            type=CategoryType.expense,
            item_name="Фриланс проект",
        )
        tx.category = old_cat

        # 1st scalar -> tx, 2nd scalar -> None (no existing alias)
        session.scalar = AsyncMock(side_effect=[tx, None])
        session.get = AsyncMock(return_value=User(id=555, currency="KZT", initial_balance=0.0))
        added_objs = []
        session.add = MagicMock(side_effect=lambda o: added_objs.append(o))
        session.commit = AsyncMock()

        cb = AsyncMock()
        cb.data = f"tx_toggle:{tx_id}"
        cb.from_user = MagicMock(id=555)

        with patch("src.bot.handlers.tx_actions.CategoryService") as mock_cs_cls, \
             patch("src.bot.handlers.tx_actions.TransactionService") as mock_ts_cls:
            mock_cs = mock_cs_cls.return_value
            mock_cs.find_by_name = AsyncMock(return_value=None)
            mock_cs.get_categories = AsyncMock(return_value=[new_cat])
            mock_ts = mock_ts_cls.return_value
            mock_ts.get_user_balance = AsyncMock(return_value={"current_balance": 20000.0})

            await handle_tx_toggle(cb, session)

        aliases = [o for o in added_objs if isinstance(o, UserItemAlias)]
        self.assertEqual(len(aliases), 1)
        expected_hash = blind_index("Фриланс проект")
        self.assertEqual(aliases[0].item_name_normalized, expected_hash)
        self.assertNotEqual(aliases[0].item_name_normalized, "фриланс проект")

    async def test_dynamic_few_shots_skips_db_when_no_tags_match(self):
        session = AsyncMock()
        svc = DynamicContextService(session)
        res = await svc.get_few_shots_for_query("голос")
        self.assertEqual(res, [])
        session.scalars.assert_not_called()

    async def test_classify_user_fact_instant_rule_skips_llm(self):
        ai = AIService(api_key="test")
        client_mock = MagicMock()
        client_mock.aio.models.generate_content = AsyncMock()
        ai.client = client_mock

        res = await ai.classify_user_fact("Хочу накопить 2 000 000 на отпуск", user_id=77)
        self.assertEqual(res["category"], "goal")
        client_mock.aio.models.generate_content.assert_not_called()

    async def test_generate_financial_advice_ttl_cache_and_force_refresh(self):
        ai = AIService(api_key="test")
        client_mock = MagicMock()
        resp_mock = MagicMock()
        resp_mock.text = '{"where_to_cut": "Сократите кафе", "where_to_save": "На вклад", "what_to_watch": "Подушка"}'
        client_mock.aio.models.generate_content = AsyncMock(return_value=resp_mock)
        ai.client = client_mock

        from types import SimpleNamespace
        summary = SimpleNamespace(
            period="month",
            period_label="Октябрь 2026",
            is_family=False,
            currency="KZT",
            total_income=500000.0,
            total_expense=200000.0,
            net_savings=300000.0,
            saving_rate=60.0,
            current_liquid_balance=300000.0,
            total_deposit_balance=100000.0,
            total_credit_debt=0.0,
            monthly_credit_payment=0.0,
            debt_burden_ratio=0.0,
            runway_months=2.0,
            top_category_name="Еда вне дома",
            top_category_amount=80000.0,
            top_category_share=40.0,
            top_categories=[],
        )

        r1 = await ai.generate_financial_advice(summary, user_id=42, user_facts=["Цель: отпуск"])
        r2 = await ai.generate_financial_advice(summary, user_id=42, user_facts=["Цель: отпуск"])
        self.assertEqual(r1, r2)
        self.assertEqual(client_mock.aio.models.generate_content.call_count, 1)

        await ai.generate_financial_advice(summary, user_id=42, user_facts=["Цель: отпуск"], force_refresh=True)
        self.assertEqual(client_mock.aio.models.generate_content.call_count, 2)


if __name__ == "__main__":
    unittest.main()
