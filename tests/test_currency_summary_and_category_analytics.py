from __future__ import annotations

import os
import types
import unittest
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException

from src.api.v1.analytics import get_category_monthly_analytics
from src.bot.messages import format_summary_card
from src.models.category import Category, CategoryType
from src.models.user import User
from src.services.ai_service import AIService
from src.services.report_service import AnalyticsSummaryData, ReportService


class TestCurrencyDepositsInSummaries(unittest.IsolatedAsyncioTestCase):
    async def test_get_agent_analytics_multi_currency_deposits_and_runway(self):
        session = AsyncMock()
        service = ReportService(session)
        user = User(id=42, initial_balance=100000.0, currency="KZT")
        session.get.return_value = user

        cf_mock = MagicMock(expense=250000.0, income=500000.0)
        cat_mock = MagicMock(all=MagicMock(return_value=[]))
        # Liquid balance = 100k + 500k - 250k - 100k + 0 = 250 000 KZT
        l_mock = MagicMock(liquid_inc=500000.0, exp=250000.0, tout=100000.0, tin=0.0)

        # Active deposits: 500 000 KZT + 1 000 USD + 0 EUR (closed/empty)
        dep_rows = [
            MagicMock(currency="USD", total=1000.0),
            MagicMock(currency="KZT", total=500000.0),
            MagicMock(currency="EUR", total=0.0),
        ]
        dep_mock = MagicMock(all=MagicMock(return_value=dep_rows))
        cr_mock = MagicMock(debt=0.0, payment=0.0)

        session.execute = AsyncMock(
            side_effect=[
                MagicMock(one=MagicMock(return_value=cf_mock)),
                cat_mock,
                MagicMock(one=MagicMock(return_value=l_mock)),
                dep_mock,
                MagicMock(one=MagicMock(return_value=cr_mock)),
            ]
        )

        summary = await service.get_agent_analytics(user_id=42, period="month")

        # KZT comes first (base currency), then USD; zero-balance EUR is excluded
        self.assertEqual(list(summary.deposits_by_currency.keys()), ["KZT", "USD"])
        self.assertEqual(summary.deposits_by_currency["KZT"], 500000.0)
        self.assertEqual(summary.deposits_by_currency["USD"], 1000.0)
        # 500 000 KZT + (1 000 USD * 500) = 1 000 000 KZT
        self.assertEqual(summary.total_deposit_balance, 1000000.0)
        # Cushion = 250 000 + 1 000 000 = 1 250 000 KZT; monthly expense = 250 000 -> runway = 5.0 months
        self.assertEqual(summary.runway_months, 5.0)

    def test_format_summary_card_renders_mixed_and_foreign_only_deposits(self):
        # 1. Mixed KZT + USD + EUR
        mixed = AnalyticsSummaryData(
            period="month",
            period_label="Октябрь 2026",
            currency="KZT",
            total_expense=150000.0,
            total_income=300000.0,
            net_savings=150000.0,
            saving_rate=50.0,
            top_category_name="Продукты",
            top_category_amount=60000.0,
            top_category_share=40.0,
            top_categories=[{"name": "Продукты", "amount": 60000.0, "share": 40.0}],
            current_liquid_balance=200000.0,
            total_deposit_balance=1270000.0,
            total_credit_debt=0.0,
            monthly_credit_payment=0.0,
            debt_burden_ratio=0.0,
            runway_months=9.8,
            is_family=False,
            deposits_by_currency={"KZT": 500000.0, "USD": 1000.0, "EUR": 500.0},
        )
        card_mixed = format_summary_card(mixed, period_label="на текущую дату")
        self.assertIn("500 000.00 ₸ • 1 000.00 $ • 500.00 €", card_mixed)
        self.assertIn("(≈ 1 270 000.00 ₸)", card_mixed)

        # 2. Foreign-only deposit (0 KZT, 1 500 USD)
        usd_only = AnalyticsSummaryData(
            period="month",
            period_label="Октябрь 2026",
            currency="KZT",
            total_expense=150000.0,
            total_income=300000.0,
            net_savings=150000.0,
            saving_rate=50.0,
            top_category_name=None,
            top_category_amount=0.0,
            top_category_share=0.0,
            top_categories=[],
            current_liquid_balance=100000.0,
            total_deposit_balance=750000.0,
            total_credit_debt=0.0,
            monthly_credit_payment=0.0,
            debt_burden_ratio=0.0,
            runway_months=5.7,
            is_family=False,
            deposits_by_currency={"USD": 1500.0},
        )
        card_usd = format_summary_card(usd_only)
        self.assertIn("<b>1 500.00 $</b> (≈ 750 000.00 ₸)", card_usd)

        # 3. KZT-only deposit (no redundant ≈ suffix)
        kzt_only = AnalyticsSummaryData(
            period="month",
            period_label="Октябрь 2026",
            currency="KZT",
            total_expense=150000.0,
            total_income=300000.0,
            net_savings=150000.0,
            saving_rate=50.0,
            top_category_name=None,
            top_category_amount=0.0,
            top_category_share=0.0,
            top_categories=[],
            current_liquid_balance=100000.0,
            total_deposit_balance=500000.0,
            total_credit_debt=0.0,
            monthly_credit_payment=0.0,
            debt_burden_ratio=0.0,
            runway_months=4.0,
            is_family=False,
            deposits_by_currency={"KZT": 500000.0},
        )
        card_kzt = format_summary_card(kzt_only)
        self.assertIn("• 🏦 Депозиты и сбережения: <b>500 000.00 ₸</b>", card_kzt)
        self.assertNotIn("≈", card_kzt)

    def test_ai_advice_cache_key_includes_currency_deposits_and_handles_magicmock(self):
        s1 = types.SimpleNamespace(
            period="month",
            is_family=False,
            currency="KZT",
            total_income=300000.0,
            total_expense=100000.0,
            current_liquid_balance=200000.0,
            total_deposit_balance=500000.0,
            deposits_by_currency={"KZT": 500000.0},
            total_credit_debt=0.0,
            top_category_name="Продукты",
        )
        s2 = types.SimpleNamespace(
            period="month",
            is_family=False,
            currency="KZT",
            total_income=300000.0,
            total_expense=100000.0,
            current_liquid_balance=200000.0,
            total_deposit_balance=500000.0,
            deposits_by_currency={"USD": 1000.0},
            total_credit_debt=0.0,
            top_category_name="Продукты",
        )
        key1 = AIService._build_advice_cache_key(1, s1, None)
        key2 = AIService._build_advice_cache_key(1, s2, None)
        self.assertNotEqual(key1, key2)

        # MagicMock without dict deposits_by_currency must not crash
        m = MagicMock()
        m.period = "month"
        m.is_family = False
        m.currency = "KZT"
        m.total_income = 100.0
        m.total_expense = 50.0
        m.current_liquid_balance = 50.0
        m.total_deposit_balance = 0.0
        m.total_credit_debt = 0.0
        m.top_category_name = None
        key_mock = AIService._build_advice_cache_key(1, m, None)
        self.assertIsInstance(key_mock, tuple)


class TestSingleCategoryMonthlyAnalytics(unittest.IsolatedAsyncioTestCase):
    async def test_get_category_monthly_dynamics_personal_and_partner_custom_categories(self):
        session = AsyncMock()
        service = ReportService(session)
        now = datetime.now(timezone.utc)
        cur_month_dt = datetime(now.year, now.month, 1, tzinfo=timezone.utc)

        # Simulate SQL rows: 'Продукты' (system) + 'Детский сад' (partner custom category)
        rows = [
            MagicMock(m_date=cur_month_dt, cat_name="Продукты", total=85000.0),
            MagicMock(m_date=cur_month_dt, cat_name="Детский сад", total=120000.0),
        ]
        session.execute = AsyncMock(return_value=MagicMock(all=MagicMock(return_value=rows)))

        sys_cats = [
            Category(id=1, name="Продукты", type=CategoryType.expense, is_system=True),
            Category(id=2, name="Транспорт", type=CategoryType.expense, is_system=True),
        ]
        with patch.object(
            CategoryService_target := __import__(
                "src.services.report_service", fromlist=["CategoryService"]
            ).CategoryService,
            "get_categories",
            new=AsyncMock(return_value=sys_cats),
        ):
            data = await service.get_category_monthly_dynamics(
                user_id=10,
                family_group_id=uuid.uuid4(),
                months_count=6,
            )

        self.assertEqual(data["months_count"], 6)
        self.assertEqual(len(data["months"]), 6)
        # Top spent category over 6 months becomes default_category
        self.assertEqual(data["default_category"], "Детский сад")
        self.assertIn("Продукты", data["series_by_category"])
        self.assertIn("Детский сад", data["series_by_category"])
        self.assertIn("Транспорт", data["series_by_category"])
        self.assertEqual(len(data["series_by_category"]["Продукты"]), 6)
        self.assertEqual(data["series_by_category"]["Продукты"][-1], 85000.0)
        self.assertEqual(data["series_by_category"]["Транспорт"], [0.0] * 6)

    async def test_api_category_monthly_enforces_family_guard(self):
        session = AsyncMock()
        solo_user = User(id=99, currency="KZT", family_group_id=None)
        with self.assertRaises(HTTPException) as ctx:
            await get_category_monthly_analytics(
                family=True,
                months=6,
                session=session,
                current_user=solo_user,
            )
        self.assertEqual(ctx.exception.status_code, 400)

    def test_frontend_static_assets_contain_single_category_chart_and_cache_bump(self):
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src", "static"))
        with open(os.path.join(base_dir, "index.html"), "r", encoding="utf-8") as f:
            html = f.read()
        with open(os.path.join(base_dir, "app.js"), "r", encoding="utf-8") as f:
            js = f.read()
        with open(os.path.join(base_dir, "styles.css"), "r", encoding="utf-8") as f:
            css = f.read()

        self.assertIn("styles.css?v=2.30", html)
        self.assertIn("app.js?v=2.30", html)
        self.assertEqual(html.count('<option value="ILS">₪ ILS</option>'), 3)
        self.assertIn('data-currency="ILS">₪ ILS</button>', html)
        self.assertIn("ILS: '₪'", js)
        self.assertIn(".currency-grid", css)
        topbar_chunk = html.split('<header class="app-topbar">')[1].split("</header>")[0]
        self.assertNotIn('id="settingsBtn"', topbar_chunk)
        balance_card_chunk = html.split('<div id="opsPersonalView">')[1].split('<div class="header-summary">')[0]
        self.assertIn('class="balance-card-top"', balance_card_chunk)
        self.assertIn('id="settingsBtn"', balance_card_chunk)
        self.assertIn(".balance-card-top", css)
        self.assertIn("body.theme-light .settings-btn", css)
        self.assertIn('id="analyticsCategoryBtn"', html)
        self.assertIn("<span>Категория</span>", html)
        self.assertIn('id="categoryBarChartContainer"', html)

        self.assertIn("/api/v1/analytics/category-monthly", js)
        self.assertIn("catBarGradient", js)
        self.assertIn("selectAnalyticsCategory", js)
        self.assertIn(".analytics-cat-btn", css)



    def test_fact_category_custom_picker_and_tx_history_filter(self):
        from pathlib import Path
        repo_root = Path(__file__).resolve().parents[1]
        html = (repo_root / "src" / "static" / "index.html").read_text(encoding="utf-8")
        js = (repo_root / "src" / "static" / "app.js").read_text(encoding="utf-8")
        css = (repo_root / "src" / "static" / "styles.css").read_text(encoding="utf-8")
        tx_api = (repo_root / "src" / "api" / "v1" / "transactions.py").read_text(encoding="utf-8")

        # 1. Fact modal uses custom picker trigger instead of native <select>
        self.assertNotIn('<select id="factCategorySelect"', html)
        self.assertIn('<input type="hidden" id="factCategorySelect"', html)
        self.assertIn('id="factCategoryPickerTrigger"', html)
        self.assertIn('id="selectedFactCategoryIcon"', html)
        self.assertIn('id="selectedFactCategoryName"', html)

        # Ensure categorySheetOverlay comes after factModal in DOM so it stacks on top
        self.assertGreater(html.index('id="categorySheetOverlay"'), html.index('id="factModal"'))
        self.assertIn("z-index: 1200;", css)

        # 2. Transaction history toolbar has category filter buttons next to refresh buttons
        self.assertIn('id="txCategoryFilterBtn"', html)
        self.assertIn('id="txCategoryFilterLabel"', html)
        self.assertIn('id="familyTxCategoryFilterBtn"', html)
        self.assertIn(".toolbar-actions", css)
        self.assertIn(".tx-filter-btn.active-filter", css)

        # 3. JS & Backend API support
        self.assertIn("FACT_CATEGORY_OPTIONS", js)
        self.assertIn("openFactCategoryPicker", js)
        self.assertIn("openTxCategoryFilterPicker", js)
        self.assertIn("Путешествия", js)
        from src.services.category_service import DEFAULT_CATEGORIES
        from src.models.category import CategoryType
        self.assertIn(("Путешествия", CategoryType.expense), DEFAULT_CATEGORIES)
        self.assertIn("category_name: Optional[str] = Query(None", tx_api)
        self.assertIn("category_id: Optional[int] = Query(None", tx_api)


if __name__ == "__main__":
    unittest.main()
