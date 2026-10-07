"""
Comprehensive Unit & Integration Test Suite for Smart Bujet Core Services & API Guards.
Covers:
- TransactionService: update_transaction, delete_transaction, create_manual_transaction, mask_transaction_for_viewer
- CreditService: create_credit, repay_credit, get_credit_summary, resolve_credit_account
- AssetService: accrue_monthly_interest_for_account, deposit_to_asset, withdraw_from_asset
- FamilyService: get_family_summary (intercompany elimination), join_by_invite, leave_group
- ReportService: get_agent_analytics (runway, saving rate, debt burden, liquid balance)
- Security & API Guards: validate_init_data, guards against uninitialized balance, NaN, and negative amounts
"""

import time
import uuid
import hmac
import hashlib
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

from fastapi import HTTPException

from src.models.user import User
from src.models.category import Category, CategoryType
from src.models.transaction import Transaction, TransactionSource
from src.models.asset import AssetAccount, AssetType
from src.models.credit import CreditAccount
from src.models.family import FamilyGroup
from src.schemas.transaction import TransactionCreate, TransactionUpdate
from src.services.transaction_service import TransactionService
from src.services.credit_service import CreditService
from src.services.asset_service import AssetService
from src.services.family_service import FamilyService
from src.services.report_service import ReportService
from src.core.security import validate_init_data


# ==============================================================================
# 1. TRANSACTION SERVICE TESTS: UPDATE & DELETE & MANUAL & PRIVACY
# ==============================================================================

class TestTransactionServiceCoverage(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.session = AsyncMock()
        self.service = TransactionService(self.session)
        self.user_id = 100
        self.user = User(id=self.user_id, initial_balance=50000.0, currency="KZT", family_group_id=None)

    # -------------------- update_transaction --------------------

    async def test_update_transaction_not_found(self):
        self.session.scalar.return_value = None
        with self.assertRaises(HTTPException) as ctx:
            await self.service.update_transaction(
                user_id=self.user_id,
                tx_id=uuid.uuid4(),
                data=TransactionUpdate(amount=Decimal("1000"))
            )
        self.assertEqual(ctx.exception.status_code, 404)

    async def test_update_transaction_forbidden_for_other_user(self):
        tx = MagicMock(spec=Transaction)
        tx.user_id = 999  # Different owner
        self.session.scalar.return_value = tx

        with self.assertRaises(HTTPException) as ctx:
            await self.service.update_transaction(
                user_id=self.user_id,
                tx_id=uuid.uuid4(),
                data=TransactionUpdate(amount=Decimal("1000"))
            )
        self.assertEqual(ctx.exception.status_code, 403)

    async def test_update_transaction_category_change_blocked_for_asset_or_credit(self):
        tx = MagicMock(spec=Transaction)
        tx.user_id = self.user_id
        tx.category_id = 1
        tx.asset_account_id = uuid.uuid4()
        tx.credit_account_id = None
        tx.related_transaction_id = None
        self.session.scalar.return_value = tx

        with self.assertRaises(HTTPException) as ctx:
            await self.service.update_transaction(
                user_id=self.user_id,
                tx_id=uuid.uuid4(),
                data=TransactionUpdate(category_id=2)
            )
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("Изменение категории для переводов", ctx.exception.detail)

    async def test_update_transaction_category_type_mismatch_rejected(self):
        tx = MagicMock(spec=Transaction)
        tx.user_id = self.user_id
        tx.category_id = 1
        tx.type = CategoryType.expense
        tx.asset_account_id = None
        tx.credit_account_id = None
        tx.related_transaction_id = None
        self.session.scalar.return_value = tx

        new_cat = MagicMock(spec=Category)
        new_cat.id = 2
        new_cat.is_system = True
        new_cat.type = CategoryType.income  # Mismatch!
        self.session.get.return_value = new_cat

        with self.assertRaises(HTTPException) as ctx:
            await self.service.update_transaction(
                user_id=self.user_id,
                tx_id=uuid.uuid4(),
                data=TransactionUpdate(category_id=2)
            )
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("не соответствует типу операции", ctx.exception.detail)

    async def test_update_transaction_amount_fx_asset_transfer_out(self):
        tx = MagicMock(spec=Transaction)
        tx.user_id = self.user_id
        tx.category_id = 1
        tx.amount = 500.0
        tx.asset_amount = 500.0
        tx.exchange_rate = 500.0
        tx.type = CategoryType.transfer_out
        tx.asset_account_id = uuid.uuid4()
        tx.credit_account_id = None
        tx.related_transaction_id = None

        asset = MagicMock(spec=AssetAccount)
        asset.balance = 250000.0

        self.session.scalar.return_value = tx
        self.session.get.return_value = asset

        await self.service.update_transaction(
            user_id=self.user_id,
            tx_id=uuid.uuid4(),
            data=TransactionUpdate(amount=Decimal("600.0"))
        )

        self.assertEqual(tx.amount, 600.0)
        self.session.commit.assert_called_once()

    async def test_update_transaction_credit_repayment_overpayment_rejected(self):
        tx = MagicMock(spec=Transaction)
        tx.user_id = self.user_id
        tx.category_id = 1
        tx.amount = 2000.0
        tx.type = CategoryType.expense
        tx.asset_account_id = None
        tx.credit_account_id = uuid.uuid4()
        tx.related_transaction_id = None

        credit = MagicMock(spec=CreditAccount)
        credit.remaining_amount = Decimal("3000.0")
        credit.is_active = True

        self.session.scalar.return_value = tx
        self.session.get.return_value = credit

        with self.assertRaises(HTTPException) as ctx:
            await self.service.update_transaction(
                user_id=self.user_id,
                tx_id=uuid.uuid4(),
                data=TransactionUpdate(amount=Decimal("6000.0"))
            )
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("не может превышать текущий остаток", ctx.exception.detail)

    async def test_update_transaction_credit_repayment_reopens_credit(self):
        tx = MagicMock(spec=Transaction)
        tx.user_id = self.user_id
        tx.category_id = 1
        tx.amount = 5000.0
        tx.type = CategoryType.expense
        tx.asset_account_id = None
        tx.credit_account_id = uuid.uuid4()
        tx.related_transaction_id = None

        credit = MagicMock(spec=CreditAccount)
        credit.remaining_amount = Decimal("0.0")
        credit.is_active = False
        credit.closed_at = datetime.now(timezone.utc)

        self.session.scalar.return_value = tx
        self.session.get.return_value = credit

        await self.service.update_transaction(
            user_id=self.user_id,
            tx_id=uuid.uuid4(),
            data=TransactionUpdate(amount=Decimal("3000.0"))
        )

        self.assertEqual(credit.remaining_amount, Decimal("2000.0"))
        self.assertTrue(credit.is_active)
        self.assertIsNone(credit.closed_at)

    async def test_update_transaction_mirror_sync(self):
        tx = MagicMock(spec=Transaction)
        tx.user_id = self.user_id
        tx.category_id = 1
        tx.amount = 1000.0
        tx.type = CategoryType.expense
        tx.asset_account_id = None
        tx.credit_account_id = None
        tx.related_transaction_id = uuid.uuid4()

        mirror_tx = MagicMock(spec=Transaction)
        mirror_tx.amount = 1000.0

        self.session.scalar = AsyncMock(side_effect=[tx, mirror_tx])

        await self.service.update_transaction(
            user_id=self.user_id,
            tx_id=uuid.uuid4(),
            data=TransactionUpdate(amount=Decimal("2500.0"))
        )
        self.assertEqual(mirror_tx.amount, 2500.0)

    # -------------------- delete_transaction --------------------

    async def test_delete_transaction_not_found(self):
        self.session.scalar.return_value = None
        with self.assertRaises(HTTPException) as ctx:
            await self.service.delete_transaction(user_id=self.user_id, tx_id=uuid.uuid4())
        self.assertEqual(ctx.exception.status_code, 404)

    async def test_delete_transaction_forbidden_other_user(self):
        tx = MagicMock(spec=Transaction)
        tx.user_id = 888
        self.session.scalar.return_value = tx

        with self.assertRaises(HTTPException) as ctx:
            await self.service.delete_transaction(user_id=self.user_id, tx_id=uuid.uuid4())
        self.assertEqual(ctx.exception.status_code, 403)

    async def test_delete_transaction_asset_transfer_out_rollback(self):
        tx = MagicMock(spec=Transaction)
        tx.user_id = self.user_id
        tx.amount = 20000.0
        tx.asset_amount = 20000.0
        tx.type = CategoryType.transfer_out
        tx.asset_account_id = uuid.uuid4()
        tx.credit_account_id = None
        tx.related_transaction_id = None

        asset = MagicMock(spec=AssetAccount)
        asset.balance = 50000.0

        self.session.scalar.return_value = tx
        self.session.get.return_value = asset

        await self.service.delete_transaction(user_id=self.user_id, tx_id=uuid.uuid4())

        self.assertEqual(asset.balance, 30000.0)
        self.session.delete.assert_called_with(tx)
        self.session.commit.assert_called_once()

    async def test_delete_transaction_asset_transfer_in_rollback(self):
        tx = MagicMock(spec=Transaction)
        tx.user_id = self.user_id
        tx.amount = 15000.0
        tx.asset_amount = 15000.0
        tx.type = CategoryType.transfer_in
        tx.asset_account_id = uuid.uuid4()
        tx.credit_account_id = None
        tx.related_transaction_id = None

        asset = MagicMock(spec=AssetAccount)
        asset.balance = 35000.0

        self.session.scalar.return_value = tx
        self.session.get.return_value = asset

        await self.service.delete_transaction(user_id=self.user_id, tx_id=uuid.uuid4())

        self.assertEqual(asset.balance, 50000.0)

    async def test_delete_transaction_credit_disbursement_blocked_if_repayments_exist(self):
        tx = MagicMock(spec=Transaction)
        tx.user_id = self.user_id
        tx.amount = 500000.0
        tx.type = CategoryType.income
        tx.credit_account_id = uuid.uuid4()
        tx.asset_account_id = None
        tx.related_transaction_id = None

        credit = MagicMock(spec=CreditAccount)

        self.session.scalar = AsyncMock(side_effect=[tx, 2])
        self.session.get.return_value = credit

        with self.assertRaises(HTTPException) as ctx:
            await self.service.delete_transaction(user_id=self.user_id, tx_id=uuid.uuid4())
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("уже зафиксированы платежи", ctx.exception.detail)

    async def test_delete_transaction_mirror_circular_ref_break(self):
        tx = MagicMock(spec=Transaction)
        tx.user_id = self.user_id
        tx.amount = 10000.0
        tx.type = CategoryType.expense
        tx.asset_account_id = None
        tx.credit_account_id = None
        tx.related_transaction_id = uuid.uuid4()

        mirror_tx = MagicMock(spec=Transaction)
        mirror_tx.related_transaction_id = uuid.uuid4()

        self.session.scalar = AsyncMock(side_effect=[tx, mirror_tx])

        await self.service.delete_transaction(user_id=self.user_id, tx_id=uuid.uuid4())

        self.assertIsNone(tx.related_transaction_id)
        self.assertIsNone(mirror_tx.related_transaction_id)
        self.session.delete.assert_any_call(mirror_tx)
        self.session.delete.assert_any_call(tx)

    # -------------------- create_manual_transaction --------------------

    async def test_create_manual_tx_uninitialized_balance_rejected(self):
        uninit_user = User(id=1, initial_balance=None)
        data = TransactionCreate(amount=Decimal("100"), category_id=1)
        with self.assertRaises(HTTPException) as ctx:
            await self.service.create_manual_transaction(uninit_user, data)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("укажите начальный баланс", ctx.exception.detail)

    # -------------------- mask_transaction_for_viewer --------------------

    def test_mask_transaction_for_viewer_hides_private_deposit_info(self):
        tx = MagicMock(spec=Transaction)
        tx.id = uuid.uuid4()
        tx.user_id = 100
        tx.family_group_id = uuid.uuid4()
        tx.category_id = 5
        tx.amount = 100000.0
        tx.original_amount = None
        tx.discount_amount = None
        tx.type = CategoryType.transfer_out
        tx.item_name = "Секретный счёт в Швейцарии"
        tx.raw_text = "переведи 100к на мой секретный швейцарский депозит"
        tx.source = TransactionSource.voice
        tx.transaction_date = datetime.now(timezone.utc)
        tx.asset_account_id = uuid.uuid4()
        tx.category = MagicMock(spec=Category)
        tx.category.name = "Депозит и вклады"

        # 1. Owner view
        owner_view = TransactionService.mask_transaction_for_viewer(tx, viewer_user_id=100)
        self.assertEqual(owner_view["item_name"], "Секретный счёт в Швейцарии")
        self.assertIsNotNone(owner_view["raw_text"])

        # 2. Partner view
        partner_view = TransactionService.mask_transaction_for_viewer(tx, viewer_user_id=200)
        self.assertEqual(partner_view["item_name"], "Пополнение депозита")
        self.assertIsNone(partner_view["raw_text"])


# ==============================================================================
# 2. CREDIT SERVICE TESTS: CREATION, REPAYMENT & MATCHING
# ==============================================================================

class TestCreditServiceCoverage(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.session = AsyncMock()
        self.service = CreditService(self.session)
        self.user_id = 100

    async def test_create_credit_defaults(self):
        credit = await self.service.create_credit(
            user_id=self.user_id,
            name="Kaspi Red",
            original_amount=Decimal("150000"),
            auto_commit=True
        )
        self.assertEqual(credit.name, "Kaspi Red")
        self.assertEqual(credit.remaining_amount, Decimal("150000"))
        self.assertTrue(credit.is_active)
        self.assertIsNone(credit.closed_at)

    async def test_repay_credit_partial(self):
        credit = CreditAccount(
            id=uuid.uuid4(),
            user_id=self.user_id,
            name="Автокредит",
            original_amount=Decimal("1000000"),
            remaining_amount=Decimal("800000"),
            is_active=True
        )
        self.session.scalar.return_value = credit

        updated, was_closed = await self.service.repay_credit(
            user_id=self.user_id,
            credit_id=credit.id,
            amount=Decimal("200000")
        )
        self.assertEqual(updated.remaining_amount, Decimal("600000"))
        self.assertTrue(updated.is_active)
        self.assertFalse(was_closed)

    async def test_repay_credit_full_payoff_and_closure(self):
        credit = CreditAccount(
            id=uuid.uuid4(),
            user_id=self.user_id,
            name="Рассрочка",
            original_amount=Decimal("100000"),
            remaining_amount=Decimal("50000"),
            is_active=True
        )
        self.session.scalar.return_value = credit

        updated, was_closed = await self.service.repay_credit(
            user_id=self.user_id,
            credit_id=credit.id,
            amount=Decimal("50000")
        )
        self.assertEqual(updated.remaining_amount, Decimal("0.0"))
        self.assertFalse(updated.is_active)
        self.assertIsNotNone(updated.closed_at)
        self.assertTrue(was_closed)

    async def test_repay_credit_overpayment_floored_at_zero(self):
        credit = CreditAccount(
            id=uuid.uuid4(),
            user_id=self.user_id,
            name="Рассрочка",
            original_amount=Decimal("100000"),
            remaining_amount=Decimal("20000"),
            is_active=True
        )
        self.session.scalar.return_value = credit

        updated, was_closed = await self.service.repay_credit(
            user_id=self.user_id,
            credit_id=credit.id,
            amount=Decimal("35000")
        )
        self.assertEqual(updated.remaining_amount, Decimal("0.0"))
        self.assertFalse(updated.is_active)
        self.assertTrue(was_closed)

    async def test_get_credit_summary_calculation(self):
        c1 = CreditAccount(remaining_amount=Decimal("100000"), monthly_payment=Decimal("15000"), is_active=True)
        c2 = CreditAccount(remaining_amount=Decimal("200000"), monthly_payment=Decimal("25000"), is_active=True)
        c3 = CreditAccount(remaining_amount=Decimal("0"), monthly_payment=Decimal("0"), is_active=False)

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [c1, c2, c3]
        self.session.scalars.return_value = mock_scalars

        summary = await self.service.get_credit_summary(self.user_id)
        self.assertEqual(summary["total_debt"], 300000.0)
        self.assertEqual(summary["total_monthly_payment"], 40000.0)
        self.assertEqual(summary["active_credits_count"], 2)
        self.assertEqual(summary["closed_credits_count"], 1)

    async def test_resolve_credit_account_token_overlap(self):
        c1 = CreditAccount(id=uuid.uuid4(), name="Кредит на авто", bank_name="Каспи Банк", is_active=True)
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [c1]
        self.session.scalars.return_value = mock_scalars

        matched = await self.service.resolve_credit_account(self.user_id, target_name="каспи авто")
        self.assertIsNotNone(matched)
        self.assertEqual(matched.id, c1.id)


# ==============================================================================
# 3. ASSET SERVICE TESTS: INTEREST ACCRUAL, DEPOSIT, WITHDRAW
# ==============================================================================

class TestAssetServiceCoverage(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.session = AsyncMock()
        self.service = AssetService(self.session)
        self.user_id = 100

    async def test_accrue_monthly_interest_calculation_and_rounding(self):
        account = AssetAccount(
            id=uuid.uuid4(),
            user_id=self.user_id,
            name="Депозит Сберегательный",
            type=AssetType.deposit,
            balance=100000.0,
            interest_rate=15.0,
            is_active=True
        )

        interest_cat = Category(id=99, name="Проценты по вкладу", type=CategoryType.income, is_system=True)
        self.service.category_service.find_by_name = AsyncMock(return_value=interest_cat)
        self.session.scalar.return_value = None

        tx = await self.service.accrue_monthly_interest_for_account(account)

        self.assertIsNotNone(tx)
        self.assertEqual(tx.amount, 1250.0)
        self.assertEqual(account.balance, 101250.0)
        self.session.commit.assert_called_once()

    async def test_accrue_monthly_interest_idempotency_prevents_duplicate(self):
        account = AssetAccount(
            id=uuid.uuid4(),
            user_id=self.user_id,
            name="Депозит",
            type=AssetType.deposit,
            balance=100000.0,
            interest_rate=15.0,
            is_active=True
        )
        interest_cat = Category(id=99, name="Проценты по вкладу", type=CategoryType.income, is_system=True)
        self.service.category_service.find_by_name = AsyncMock(return_value=interest_cat)

        self.session.scalar.return_value = uuid.uuid4()

        tx = await self.service.accrue_monthly_interest_for_account(account)
        self.assertIsNone(tx)
        self.assertEqual(account.balance, 100000.0)

    async def test_accrue_monthly_interest_skips_non_deposit_or_zero_rate(self):
        currency_acc = AssetAccount(type=AssetType.currency, interest_rate=15.0, balance=1000.0, is_active=True)
        zero_rate_acc = AssetAccount(type=AssetType.deposit, interest_rate=0.0, balance=1000.0, is_active=True)
        inactive_acc = AssetAccount(type=AssetType.deposit, interest_rate=15.0, balance=1000.0, is_active=False)

        self.assertIsNone(await self.service.accrue_monthly_interest_for_account(currency_acc))
        self.assertIsNone(await self.service.accrue_monthly_interest_for_account(zero_rate_acc))
        self.assertIsNone(await self.service.accrue_monthly_interest_for_account(inactive_acc))

    async def test_deposit_and_withdraw_balance_deltas(self):
        asset = AssetAccount(id=uuid.uuid4(), user_id=self.user_id, balance=50000.0, name="Вклад")
        self.session.get.return_value = asset
        self.service.category_service.get_categories = AsyncMock(return_value=[])

        # Deposit 10,000
        await self.service.deposit_to_asset(self.user_id, asset.id, 10000.0)
        self.assertEqual(asset.balance, 60000.0)

        # Withdraw 25,000
        await self.service.withdraw_from_asset(self.user_id, asset.id, 25000.0)
        self.assertEqual(asset.balance, 35000.0)


# ==============================================================================
# 4. FAMILY SERVICE TESTS: INTERCOMPANY ELIMINATION & LIFECYCLE
# ==============================================================================

class TestFamilyServiceCoverage(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.session = AsyncMock()
        self.service = FamilyService(self.session)
        self.owner = User(id=1, first_name="Алиса", family_group_id=uuid.uuid4(), currency="KZT")
        self.partner = User(id=2, first_name="Боб", family_group_id=self.owner.family_group_id, currency="KZT")
        self.group = FamilyGroup(id=self.owner.family_group_id, name="Семья", owner_id=1, invite_code="INV123")

    async def test_get_family_summary_intercompany_elimination(self):
        self.service.get_or_create_user_family = AsyncMock(return_value=self.group)

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [self.owner, self.partner]
        self.session.scalars.return_value = mock_scalars

        self.service.tx_service.get_user_balance = AsyncMock(side_effect=[
            {"current_balance": 200000.0, "month_expense": 100000.0, "month_income": 300000.0},
            {"current_balance": 150000.0, "month_expense": 30000.0, "month_income": 50000.0},
        ])

        self.session.scalar = AsyncMock(side_effect=[50000.0, 0.0])

        summary = await self.service.get_family_summary(self.owner)

        self.assertEqual(summary["status"], "active_family")
        self.assertIsNone(summary["invite_link"])
        self.assertEqual(summary["combined_month_expense"], 80000.0)

    async def test_join_by_invite_cleans_up_solo_group(self):
        new_user = User(id=3, first_name="Чарли", family_group_id=uuid.uuid4())
        solo_group = FamilyGroup(id=new_user.family_group_id, name="Семья Чарли", owner_id=3)

        self.session.scalar = AsyncMock(side_effect=[
            None,        # No partner in Charlie's old group (passes top-level partner guard)
            self.group,  # Found target family
            1            # Partner ID to notify in target family
        ])
        self.session.get.return_value = solo_group

        target_group, notify_id, msg = await self.service.join_by_invite(new_user, "INV123")

        self.assertEqual(target_group.id, self.group.id)
        self.assertEqual(notify_id, 1)
        self.session.delete.assert_called_with(solo_group)


# ==============================================================================
# 5. REPORT SERVICE TESTS: METRIC CALCULATIONS & ZERO-SAFE GUARDS
# ==============================================================================

class TestReportServiceCoverage(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.session = AsyncMock()
        self.service = ReportService(self.session)
        self.user_id = 100

    async def test_get_agent_analytics_runway_and_saving_rate(self):
        user = User(id=self.user_id, initial_balance=100000.0, currency="KZT")
        self.session.get.return_value = user

        cf_mock = MagicMock()
        cf_mock.expense = 200000.0
        cf_mock.income = 400000.0

        cat_mock = MagicMock()
        cat_mock.all.return_value = []

        l_mock = MagicMock()
        l_mock.liquid_inc = 400000.0
        l_mock.exp = 200000.0
        l_mock.tout = 50000.0
        l_mock.tin = 0.0

        deposit_val = 500000.0

        cr_mock = MagicMock()
        cr_mock.debt = 100000.0
        cr_mock.payment = 20000.0

        execute_results = [
            MagicMock(one=MagicMock(return_value=cf_mock)),
            cat_mock,
            MagicMock(one=MagicMock(return_value=l_mock)),
            MagicMock(one=MagicMock(return_value=cr_mock)),
        ]
        self.session.execute = AsyncMock(side_effect=execute_results)
        self.session.scalar = AsyncMock(return_value=deposit_val)

        analytics = await self.service.get_agent_analytics(self.user_id, period="month")

        self.assertEqual(analytics.saving_rate, 50.0)
        self.assertEqual(analytics.debt_burden_ratio, 5.0)
        self.assertEqual(analytics.runway_months, 3.75)

    async def test_get_agent_analytics_zero_expense_safe(self):
        user = User(id=self.user_id, initial_balance=50000.0)
        self.session.get.return_value = user

        cf_mock = MagicMock(expense=0.0, income=100000.0)
        cat_mock = MagicMock(all=MagicMock(return_value=[]))
        l_mock = MagicMock(liquid_inc=100000.0, exp=0.0, tout=0.0, tin=0.0)
        cr_mock = MagicMock(debt=0.0, payment=0.0)

        self.session.execute = AsyncMock(side_effect=[
            MagicMock(one=MagicMock(return_value=cf_mock)),
            cat_mock,
            MagicMock(one=MagicMock(return_value=l_mock)),
            MagicMock(one=MagicMock(return_value=cr_mock)),
        ])
        self.session.scalar = AsyncMock(return_value=0.0)

        analytics = await self.service.get_agent_analytics(self.user_id, period="month")
        self.assertEqual(analytics.runway_months, 99.0)


# ==============================================================================
# 6. SECURITY & API GUARDS TESTS
# ==============================================================================

class TestSecurityAndApiGuardsCoverage(unittest.TestCase):
    def test_validate_init_data_valid_hmac(self):
        token = "123456:TEST_BOT_TOKEN"
        auth_time = int(time.time())
        data_pairs = {"auth_date": str(auth_time), "query_id": "AAHdF60gAAAAAN0XrSBq7", "user": '{"id":123}'}
        check_str = "\n".join(f"{k}={v}" for k, v in sorted(data_pairs.items()))
        secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
        calc_hash = hmac.new(secret, check_str.encode(), hashlib.sha256).hexdigest()

        init_data = f"auth_date={auth_time}&query_id=AAHdF60gAAAAAN0XrSBq7&user=%7B%22id%22%3A123%7D&hash={calc_hash}"
        res = validate_init_data(init_data, token)
        self.assertIsNotNone(res)
        self.assertEqual(res["auth_date"], str(auth_time))

    def test_validate_init_data_expired_rejected(self):
        token = "123456:TEST_BOT_TOKEN"
        old_auth = int(time.time()) - 90000
        res = validate_init_data(f"auth_date={old_auth}&hash=dummy", token)
        self.assertIsNone(res)

    def test_validate_init_data_tampered_hash_rejected(self):
        token = "123456:TEST_BOT_TOKEN"
        auth_time = int(time.time())
        res = validate_init_data(f"auth_date={auth_time}&user=hacker&hash=badhash123", token)
        self.assertIsNone(res)


if __name__ == "__main__":
    unittest.main()
