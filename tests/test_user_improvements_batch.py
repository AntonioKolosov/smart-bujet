import unittest
from unittest.mock import AsyncMock, MagicMock
from decimal import Decimal
import uuid

from fastapi import HTTPException
from src.models.user import User
from src.models.category import Category, CategoryType
from src.models.credit import CreditAccount
from src.models.family import FamilyGroup
from src.bot.messages import BotMessages
from src.bot.handlers.summary import (
    summary_scope_selection_keyboard,
    summary_card_inline_keyboard,
    user_has_active_family,
)
from src.services.ai_service import AIService
from src.services.transaction_service import TransactionService
from src.services.family_service import FamilyService
from src.api.v1.analytics import _verify_family_access


class TestUserImprovementsBatch(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.user = User(
            id=777,
            first_name="Aiganym",
            username="aiganym",
            currency="KZT",
            initial_balance=100000.0,
            family_group_id=uuid.uuid4(),
        )

    # ----------------------------------------------------
    # 1. Credit Monthly Payment Auto-Fill
    # ----------------------------------------------------
    def test_credits_context_formatting_includes_monthly_payment(self):
        ai_service = AIService()
        credits_context = [
            {
                "id": str(uuid.uuid4()),
                "name": "Халыковский кредит",
                "remaining_amount": 450000.0,
                "monthly_payment": 45000.0,
                "currency": "KZT",
            }
        ]
        formatted = ai_service._format_credits_context(credits_context)
        self.assertIn("Халыковский кредит", formatted)
        self.assertIn("ежемесячный платеж: 45000.0 KZT", formatted)
        self.assertIn("АВТОМАТИЧЕСКИ укажи сумму", formatted)

    async def test_transaction_service_auto_fills_monthly_payment_if_amount_zero(self):
        session = AsyncMock()
        service = TransactionService(session=session)
        service.ai_service = MagicMock()
        service.credit_service = MagicMock()
        service.category_service = MagicMock()
        service.asset_service = MagicMock()
        service.dynamic_service = MagicMock()
        service.dynamic_service.get_few_shots_for_query = AsyncMock(return_value=[])
        service.dynamic_service.format_few_shots_prompt = MagicMock(return_value="")

        credit = CreditAccount(
            id=uuid.uuid4(),
            user_id=self.user.id,
            name="Халыковский кредит",
            original_amount=500000.0,
            remaining_amount=450000.0,
            monthly_payment=45000.0,
            currency="KZT",
        )
        service.credit_service.get_user_credits = AsyncMock(return_value=[credit])
        service.credit_service.resolve_credit_account = AsyncMock(return_value=credit)
        service.credit_service.repay_credit = AsyncMock(return_value=(credit, False))

        cat = Category(id=5, name="Погашение кредита", type=CategoryType.expense)
        service.category_service.get_categories = AsyncMock(return_value=[cat])
        service.category_service.find_by_name = AsyncMock(return_value=cat)
        service.asset_service.get_accessible_assets = AsyncMock(return_value=[])

        # AI returned repayment but without numeric amount (0.0)
        service.ai_service.parse_voice = AsyncMock(return_value={
            "is_financial": True,
            "items": [
                {
                    "item_name": "оплатил ежемесячный платеж Халыковский кредит",
                    "amount": 0.0,
                    "type": "expense",
                    "category": "Погашение кредита",
                    "credit_action": "repay",
                    "target_credit_name": "Халыковский кредит",
                }
            ]
        })

        async def mock_get(model, pk):
            if model == User:
                return self.user
            if model == Category:
                return cat
            return None
        session.get = AsyncMock(side_effect=mock_get)
        session.scalar = AsyncMock(return_value=None)
        session.scalars = MagicMock()
        mock_res = MagicMock()
        mock_res.all.return_value = [cat]
        session.scalars.return_value = mock_res

        txs = await service.process_voice(user_id=self.user.id, audio_bytes=b"dummy")
        self.assertEqual(len(txs), 1)
        self.assertEqual(txs[0].amount, 45000.0)
        self.assertEqual(txs[0].credit_account_id, credit.id)
        service.credit_service.repay_credit.assert_called_once()

    # ----------------------------------------------------
    # 2. Registration / Onboarding Clarity
    # ----------------------------------------------------
    def test_onboarding_messages_clarify_cash_and_cards_and_deposits(self):
        ask_text = BotMessages.ask_initial_balance()
        self.assertIn("в обороте", ask_text)
        self.assertIn("на всех банковских картах и наличными", ask_text)
        self.assertIn("Депозиты, вклады и сбережения сюда включать не нужно", ask_text)

        set_text = BotMessages.initial_balance_set(500000.0, "KZT")
        self.assertIn("в обороте установлен", set_text)
        self.assertIn("Депозиты", set_text)

        guard_text = BotMessages.guard_set_balance_first()
        self.assertIn("карты + наличные", guard_text)
        self.assertIn("Депозиты и накопления добавляются отдельно", guard_text)

    # ----------------------------------------------------
    # 3. Summary Scope Selection & Card Guard
    # ----------------------------------------------------
    def test_summary_keyboards_hide_family_when_solo(self):
        # Scope selection keyboard
        solo_kb = summary_scope_selection_keyboard(has_family=False)
        buttons_solo = [b.text for row in solo_kb.inline_keyboard for b in row]
        self.assertIn("👤 Личная", buttons_solo)
        self.assertNotIn("👨‍👩‍👧‍👦 Семейная", buttons_solo)

        family_kb = summary_scope_selection_keyboard(has_family=True)
        buttons_fam = [b.text for row in family_kb.inline_keyboard for b in row]
        self.assertIn("👤 Личная", buttons_fam)
        self.assertIn("👨‍👩‍👧‍👦 Семейная", buttons_fam)

        # Personal summary card keyboard
        solo_card_kb = summary_card_inline_keyboard("p", has_family=False)
        card_buttons_solo = [b.text for row in solo_card_kb.inline_keyboard for b in row]
        self.assertNotIn("👨‍👩‍👧‍👦 Семейная", card_buttons_solo)
        self.assertIn("📋 В меню", card_buttons_solo)

        family_card_kb = summary_card_inline_keyboard("p", has_family=True)
        card_buttons_fam = [b.text for row in family_card_kb.inline_keyboard for b in row]
        self.assertIn("👨‍👩‍👧‍👦 Семейная", card_buttons_fam)
        self.assertIn("📋 В меню", card_buttons_fam)

    async def test_user_has_active_family_helper(self):
        session = AsyncMock()
        # Solo user (count < 2)
        session.scalar = AsyncMock(return_value=1)
        has_fam = await user_has_active_family(session, self.user)
        self.assertFalse(has_fam)

        # Partnered user (count >= 2)
        session.scalar = AsyncMock(return_value=2)
        has_fam = await user_has_active_family(session, self.user)
        self.assertTrue(has_fam)

    # ----------------------------------------------------
    # 4. Analytics Family Guard
    # ----------------------------------------------------
    async def test_verify_family_access_guard_raises_for_unpartnered_user(self):
        session = AsyncMock()

        # User without family group
        solo_user = User(id=888, family_group_id=None)
        with self.assertRaises(HTTPException) as ctx:
            await _verify_family_access(solo_user, session)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(ctx.exception.detail, "Вы не состоите в семейной группе")

        # User in solo family group (count = 1)
        session.scalar = AsyncMock(return_value=1)
        with self.assertRaises(HTTPException) as ctx:
            await _verify_family_access(self.user, session)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(ctx.exception.detail, "Вы не состоите в семейной группе")

        # User in partnered family group (count = 2)
        session.scalar = AsyncMock(return_value=2)
        gid = await _verify_family_access(self.user, session)
        self.assertEqual(gid, self.user.family_group_id)

    # ----------------------------------------------------
    # 5. Family Cross-Invite Race Condition Guard
    # ----------------------------------------------------
    async def test_join_by_invite_rejects_immediately_if_user_already_has_partner(self):
        session = AsyncMock()
        service = FamilyService(session=session)

        # Partner query returns an existing partner id
        partner_id = 999
        session.scalar = AsyncMock(return_value=partner_id)

        group, notified_id, msg = await service.join_by_invite(
            user=self.user,
            invite_code="DELETED_OR_CROSS_INVITE_CODE"
        )
        self.assertIsNone(group)
        self.assertIsNone(notified_id)
        self.assertEqual(msg, "Вы уже состоите в семейной группе.")


if __name__ == "__main__":
    unittest.main()
