from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.core.config import settings
from src.models.user import User
from src.models.transaction import Transaction
from src.models.category import Category, CategoryType
from src.services.category_service import CategoryService
from src.services.transaction_service import TransactionService

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None

logger = logging.getLogger(__name__)


def clean_gemini_json(raw_text: str) -> dict[str, Any]:
    """Strip markdown codeblocks and parse JSON safely."""
    text = raw_text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE).strip()
    try:
        return json.loads(text)
    except Exception as exc:
        logger.warning("Failed to decode JSON from Gemini: %s. Raw: %s", exc, raw_text[:200])
        return {}


class BankStatementService:
    def __init__(self, session: AsyncSession, api_key: str | None = None, model_name: str | None = None):
        self.session = session
        self.api_key = api_key or settings.google_token
        self.client = genai.Client(api_key=self.api_key) if (self.api_key and genai is not None) else None
        self.model_name = model_name or settings.gemini_model

    async def parse_single_pdf(self, pdf_bytes: bytes, filename: str) -> dict[str, Any]:
        """Parse one bank statement PDF using Gemini multimodal capabilities."""
        if not self.client:
            logger.error("Gemini client not initialized for BankStatementService")
            return {"error": "AI service unavailable", "transactions": []}

        prompt = (
            "Ты специализированный финансовый анализатор банковских выписок (PDF) приложения Smart Bujet.\n"
            "Твоя задача — извлечь из предоставленной банковской выписки все финансовые операции, "
            "начальный и конечный баланс, валюту счета, банк и период выписки.\n\n"
            "СТРОГИЕ ПРАВИЛА:\n"
            "1. Извлеки все строки операций из выписки. Для каждой операции укажи:\n"
            "   - 'date': дата операции в формате 'YYYY-MM-DD' (или 'YYYY-MM-DDTHH:MM:SS').\n"
            "   - 'amount': сумма в виде положительного числа (float/int).\n"
            "   - 'type': 'expense' (списание, покупка, комиссия, исходящий перевод) или 'income' (пополнение, зарплата, входящий перевод, кешбэк, проценты).\n"
            "   - 'item_name': получатель/магазин/описание (например 'Magnum', 'Yandex Go', 'Зарплата', 'Kaspi Pay').\n"
            "   - 'category': категория из стандартных: 'Продукты', 'Транспорт', 'Кафе и рестораны', 'Здоровье', 'Развлечения', 'Шоппинг', 'Коммунальные услуги', 'Связь', 'Подписки', 'Зарплата', 'Денежный перевод', 'Прочее'.\n"
            "2. Извлеки метаданные выписки:\n"
            "   - 'bank_name': название банка (например 'Kaspi Bank', 'Halyk Bank', 'ForteBank', 'Сбербанк', 'Тинькофф').\n"
            "   - 'currency': валюта (например 'KZT', 'USD', 'RUB', 'EUR'). По умолчанию 'KZT'.\n"
            "   - 'period_start': дата начала выписки 'YYYY-MM-DD'.\n"
            "   - 'period_end': дата конца выписки 'YYYY-MM-DD'.\n"
            "   - 'starting_balance': начальный остаток (float или null).\n"
            "   - 'closing_balance': итоговый остаток на конец периода (float или null).\n\n"
            "Верни СТРОГО валидный JSON без markdown-тегов:\n"
            "{\n"
            '  "bank_name": "Kaspi Bank",\n'
            '  "currency": "KZT",\n'
            '  "period_start": "2024-01-01",\n'
            '  "period_end": "2024-12-31",\n'
            '  "starting_balance": 50000.0,\n'
            '  "closing_balance": 125000.0,\n'
            '  "transactions": [\n'
            '    {"date": "2024-01-05", "amount": 3200.0, "type": "expense", "item_name": "Magnum", "category": "Продукты"}\n'
            '  ]\n'
            "}"
        )

        try:
            pdf_part = types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf")
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=self.model_name,
                contents=[prompt, pdf_part],
            )
            raw_text = response.text or ""
            parsed = clean_gemini_json(raw_text)
            if not isinstance(parsed, dict):
                return {"error": "Invalid response format", "transactions": []}
            return parsed
        except Exception as exc:
            logger.error("Failed to parse PDF statement '%s': %s", filename, exc)
            return {"error": str(exc), "transactions": []}

    async def import_statements(
        self,
        user_id: int,
        files: list[tuple[str, bytes]],
    ) -> dict[str, Any]:
        """
        Process one or multiple PDF bank statements for the user,
        persist transactions, calibrate initial balance to match closing balance,
        and return summary stats.
        """
        user = await self.session.get(User, user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")

        # Ensure categories exist
        cat_service = CategoryService(self.session)
        categories = await cat_service.get_all_categories()
        cat_map: dict[str, Category] = {c.name.lower(): c for c in categories}
        default_expense_cat = cat_map.get("прочее") or (categories[0] if categories else None)
        default_income_cat = cat_map.get("зарплата") or cat_map.get("доход") or default_expense_cat

        all_tx_records: list[dict[str, Any]] = []
        bank_names: set[str] = set()
        detected_currencies: list[str] = []
        latest_closing_balance: float | None = None
        latest_statement_date: datetime | None = None
        earliest_statement_date: datetime | None = None

        for filename, pdf_bytes in files:
            statement_data = await self.parse_single_pdf(pdf_bytes, filename)
            bank = statement_data.get("bank_name")
            if bank:
                bank_names.add(bank)

            currency = statement_data.get("currency")
            if currency:
                detected_currencies.append(currency.upper())

            # Track dates and closing balance
            p_end_str = statement_data.get("period_end")
            p_start_str = statement_data.get("period_start")
            
            p_end = None
            if p_end_str:
                try:
                    p_end = datetime.fromisoformat(p_end_str).replace(tzinfo=timezone.utc)
                except Exception:
                    pass

            p_start = None
            if p_start_str:
                try:
                    p_start = datetime.fromisoformat(p_start_str).replace(tzinfo=timezone.utc)
                except Exception:
                    pass

            if p_start and (earliest_statement_date is None or p_start < earliest_statement_date):
                earliest_statement_date = p_start

            if p_end and (latest_statement_date is None or p_end > latest_statement_date):
                latest_statement_date = p_end
                cb = statement_data.get("closing_balance")
                if cb is not None:
                    try:
                        latest_closing_balance = float(cb)
                    except Exception:
                        pass

            # Gather transactions
            for tx in statement_data.get("transactions", []):
                if not isinstance(tx, dict):
                    continue
                amt = tx.get("amount")
                if amt is None:
                    continue
                try:
                    num_amt = abs(float(amt))
                    if num_amt <= 0:
                        continue
                except Exception:
                    continue

                tx_date_raw = tx.get("date")
                tx_date = datetime.now(timezone.utc)
                if tx_date_raw:
                    try:
                        parsed_dt = datetime.fromisoformat(str(tx_date_raw))
                        if parsed_dt.tzinfo is None:
                            parsed_dt = parsed_dt.replace(tzinfo=timezone.utc)
                        tx_date = parsed_dt
                    except Exception:
                        pass

                all_tx_records.append({
                    "date": tx_date,
                    "amount": Decimal(str(num_amt)),
                    "type": CategoryType.income if tx.get("type") == "income" else CategoryType.expense,
                    "item_name": str(tx.get("item_name") or "Операция по выписке").strip()[:200],
                    "category": str(tx.get("category") or "").strip(),
                })

        if not all_tx_records:
            return {
                "success": False,
                "error": "Не удалось обнаружить операции в загруженных выписках.",
                "total_count": 0,
            }

        # Sort transactions chronologically
        all_tx_records.sort(key=lambda x: x["date"])

        # Determine start/end of period from actual transactions if metadata missing
        if earliest_statement_date is None:
            earliest_statement_date = all_tx_records[0]["date"]
        if latest_statement_date is None:
            latest_statement_date = all_tx_records[-1]["date"]

        # Insert transactions into database with raw_text=None (data minimization)
        total_period_expense = Decimal("0")
        total_period_income = Decimal("0")

        for item in all_tx_records:
            cat_name = item["category"].lower()
            matched_cat = cat_map.get(cat_name)
            if not matched_cat:
                matched_cat = default_income_cat if item["type"] == CategoryType.income else default_expense_cat

            tx_obj = Transaction(
                user_id=user.id,
                category_id=matched_cat.id if matched_cat else 1,
                amount=item["amount"],
                type=item["type"],
                item_name=item["item_name"],
                transaction_date=item["date"],
                created_at=item["date"],
                raw_text=None,
            )
            self.session.add(tx_obj)

            if item["type"] == CategoryType.income:
                total_period_income += item["amount"]
            else:
                total_period_expense += item["amount"]

        # Set user currency if detected
        if detected_currencies:
            user.currency = detected_currencies[0]

        # Calibrate initial balance so that live balance = latest closing balance
        net_cashflow = total_period_income - total_period_expense
        if latest_closing_balance is not None:
            calculated_initial = Decimal(str(latest_closing_balance)) - net_cashflow
            user.initial_balance = max(Decimal("0.0"), calculated_initial)
        else:
            # If statement didn't specify closing balance, set initial balance to 0 and current balance = net
            user.initial_balance = Decimal("0.0")

        await self.session.commit()

        # Compute current month metrics
        now = datetime.now(timezone.utc)
        start_current_month = datetime(now.year, now.month, 1, 0, 0, 0, tzinfo=timezone.utc)
        
        current_month_expense = sum(
            x["amount"] for x in all_tx_records
            if x["type"] == CategoryType.expense and x["date"] >= start_current_month
        )
        current_month_income = sum(
            x["amount"] for x in all_tx_records
            if x["type"] == CategoryType.income and x["date"] >= start_current_month
        )

        tx_service = TransactionService(self.session)
        live_balance_data = await tx_service.get_user_balance(user.id)

        period_label = (
            f"{earliest_statement_date.strftime('%d.%m.%Y')} — {latest_statement_date.strftime('%d.%m.%Y')}"
        )

        return {
            "success": True,
            "bank_names": list(bank_names) or ["Банк"],
            "period_label": period_label,
            "total_count": len(all_tx_records),
            "total_expense": float(total_period_expense),
            "total_income": float(total_period_income),
            "current_month_expense": float(current_month_expense),
            "current_month_income": float(current_month_income),
            "current_balance": live_balance_data["current_balance"],
            "currency": user.currency,
        }
