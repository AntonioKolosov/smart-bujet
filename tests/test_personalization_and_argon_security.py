import unittest
import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from src.models.agent_memory import FactCategory, UserAgentMemory
from src.models.asset import AssetAccount, AssetType
from src.models.category import Category, CategoryType
from src.models.transaction import Transaction, TransactionSource
from src.models.user import User
from src.services.ai_service import AIService, AIRateLimiter
from src.services.transaction_service import TransactionService
from src.api.v1.webhook import is_duplicate_update
from src.bot.handlers.start import cmd_start, on_privacy_accept, PRIVACY_AGREEMENT_TEXT
from src.bot.keyboards.inline import get_miniapp_url


class TestPersonalizationAndArgonSecurity(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.session = AsyncMock()
        self.ai_service = AIService()
        self.user = User(
            id=12345678,
            first_name="Тест",
            currency="KZT",
            initial_balance=100000.0,
            family_group_id=None
        )

    def test_fact_rule_based_classifier(self):
        # Goal
        res_goal = self.ai_service._classify_fact_rule_based("Хочу накопить 1 000 000 ₸ на отпуск в июле")
        self.assertEqual(res_goal["category"], "goal")

        # Habit
        res_habit = self.ai_service._classify_fact_rule_based("Каждое утро покупаю кофе за 1500 тенге")
        self.assertEqual(res_habit["category"], "habit")

        # Schedule
        res_sched = self.ai_service._classify_fact_rule_based("Зарплата 10-го и 25-го числа каждого месяца")
        self.assertEqual(res_sched["category"], "schedule")

        # Constraint
        res_constraint = self.ai_service._classify_fact_rule_based("Не больше 20 000 на такси в месяц")
        self.assertEqual(res_constraint["category"], "constraint")

        # Other / General
        res_other = self.ai_service._classify_fact_rule_based("Работаю удаленно, дома двое детей")
        self.assertEqual(res_other["category"], "other")

    def test_ai_rate_limiter(self):
        limiter = AIRateLimiter(max_per_minute=3, max_per_day=5)
        user_id = 999

        # First 3 calls succeed
        allowed1, _ = limiter.check_and_record(user_id)
        allowed2, _ = limiter.check_and_record(user_id)
        allowed3, _ = limiter.check_and_record(user_id)
        self.assertTrue(allowed1)
        self.assertTrue(allowed2)
        self.assertTrue(allowed3)

        # 4th call exceeds per-minute quota
        allowed4, msg = limiter.check_and_record(user_id)
        self.assertFalse(allowed4)
        self.assertIn("минутный лимит", msg)

    def test_webhook_deduplication(self):
        update_id = 987654321
        # First arrival is not duplicate
        self.assertFalse(is_duplicate_update(update_id))
        # Immediate duplicate arrival is detected
        self.assertTrue(is_duplicate_update(update_id))

    async def test_update_transaction_currency_division_formula(self):
        """
        Verify that editing a currency transaction amount uses division:
        new_asset_amt = new_amount / exchange_rate
        instead of multiplying base amount by exchange rate!
        """
        tx_service = TransactionService(self.session)

        asset = AssetAccount(
            id=uuid.uuid4(),
            user_id=self.user.id,
            name="Наличная валюта",
            type=AssetType.currency,
            currency="USD",
            balance=100.0
        )

        tx = Transaction(
            id=uuid.uuid4(),
            user_id=self.user.id,
            category_id=1,
            amount=45000.0,
            asset_amount=100.0,
            exchange_rate=450.0,
            type=CategoryType.transfer_out,
            asset_account_id=asset.id,
            item_name="Покупка валюты"
        )

        self.session.scalar = AsyncMock(return_value=tx)
        self.session.get = AsyncMock(side_effect=lambda model, mid, *args, **kwargs: asset if model == AssetAccount else tx)

        from src.schemas.transaction import TransactionUpdate
        # Change amount from 45000 to 90000 KZT (should yield 200 USD at 450 rate, not 40 500 000 USD!)
        update_data = TransactionUpdate(amount=Decimal("90000.00"))

        await tx_service.update_transaction(tx_id=tx.id, user_id=self.user.id, data=update_data)

        # 90000 / 450 = 200 USD
        self.assertEqual(tx.asset_amount, 200.0)
        # Asset balance delta: +100 USD -> 100 + 100 = 200 USD
        self.assertEqual(asset.balance, 200.0)

    async def test_raw_text_minimization_on_transaction_creation(self):
        """
        Verify that raw_text is set to None on transaction creation (data minimization).
        """
        tx_service = TransactionService(self.session)
        self.session.get = AsyncMock(return_value=self.user)
        self.session.scalar = AsyncMock(return_value=Category(id=1, name="Продукты", type=CategoryType.expense))
        tx_service.credit_service.get_user_credits = AsyncMock(return_value=[])
        tx_service._save_alias = AsyncMock()

        added_objects = []
        self.session.add = MagicMock(side_effect=lambda o: added_objects.append(o))
        self.session.commit = AsyncMock()

        with patch("src.services.transaction_service.ParserService.parse_text", return_value=(Decimal("2500"), "молоко")), \
             patch.object(tx_service, "_get_alias_category", return_value=Category(id=1, name="Продукты", type=CategoryType.expense)):
            txs = await tx_service.process_text(user_id=self.user.id, text="молоко 2500")

        self.assertEqual(len(txs), 1)
        self.assertIsNone(txs[0].raw_text)

    async def test_cmd_start_new_user_shows_user_agreement(self):
        """
        Verify /start onboarding shows mandatory User Agreement (PRIVACY_AGREEMENT_TEXT)
        and privacy:accept button for a brand-new user, with username=None.
        """
        msg = AsyncMock()
        msg.from_user = MagicMock(id=777001, first_name="Алия", username="aliya_handle")
        cmd = MagicMock(args=None)

        added_users = []
        self.session.scalar = AsyncMock(return_value=None)
        self.session.add = MagicMock(side_effect=lambda u: added_users.append(u))
        self.session.commit = AsyncMock()

        await cmd_start(msg, self.session, cmd)

        self.assertEqual(len(added_users), 1)
        self.assertIsNone(added_users[0].username)
        self.assertFalse(added_users[0].has_accepted_terms)
        msg.answer.assert_awaited_once()
        sent_text = msg.answer.call_args[0][0]
        sent_kb = msg.answer.call_args[1]["reply_markup"]
        self.assertIn("Пользовательское соглашение", sent_text)
        self.assertEqual(sent_text, PRIVACY_AGREEMENT_TEXT)
        self.assertEqual(sent_kb.inline_keyboard[0][0].callback_data, "privacy:accept")

    async def test_cmd_start_family_invite_new_user_shows_user_agreement(self):
        """
        Verify /start fam_<code> also enforces the mandatory User Agreement gate for new users.
        """
        msg = AsyncMock()
        msg.from_user = MagicMock(id=777002, first_name="Тимур", username="timur_handle")
        cmd = MagicMock(args="fam_abc123")

        self.session.scalar = AsyncMock(return_value=None)
        self.session.add = MagicMock()
        self.session.commit = AsyncMock()

        with patch("src.bot.handlers.start.FamilyService") as mock_fam_cls:
            mock_fam = mock_fam_cls.return_value
            mock_fam.join_by_invite = AsyncMock(return_value=(MagicMock(name="Семья"), None, "Вы вступили в группу!"))
            await cmd_start(msg, self.session, cmd)

        msg.answer.assert_awaited_once()
        sent_text = msg.answer.call_args[0][0]
        sent_kb = msg.answer.call_args[1]["reply_markup"]
        self.assertIn("Пользовательское соглашение", sent_text)
        self.assertEqual(sent_kb.inline_keyboard[0][0].callback_data, "privacy:accept")

    async def test_privacy_accept_transitions_to_currency_and_prod_miniapp_url(self):
        """
        Verify clicking privacy:accept sets has_accepted_terms=True and proceeds directly
        to currency selection (with zero bank statement prompt), and get_miniapp_url()
        defaults safely to production domain when MINIAPP_DOMAIN is unset.
        """
        pending_user = User(
            id=777001,
            first_name="Алия",
            currency="KZT",
            initial_balance=None,
            has_accepted_terms=False,
        )
        cb = AsyncMock()
        cb.from_user = MagicMock(id=777001)
        self.session.scalar = AsyncMock(return_value=pending_user)
        self.session.commit = AsyncMock()

        await on_privacy_accept(cb, self.session)

        self.assertTrue(pending_user.has_accepted_terms)
        cb.message.edit_text.assert_awaited_once()
        kb = cb.message.edit_text.call_args[1]["reply_markup"]
        callbacks = [btn.callback_data for row in kb.inline_keyboard for btn in row]
        self.assertIn("currency_KZT", callbacks)
        self.assertNotIn("onboard:statement", callbacks)

        from src.core.config import settings
        with patch.object(settings, "miniapp_domain", None), patch.object(settings, "domain", "localhost"):
            self.assertEqual(get_miniapp_url(), "https://85.198.89.188.sslip.io:8443/app")


if __name__ == "__main__":
    unittest.main()
