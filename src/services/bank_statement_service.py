from __future__ import annotations

import asyncio
import io
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
from src.models.transaction import Transaction, TransactionSource
from src.models.category import Category, CategoryType
from src.services.category_service import CategoryService
from src.services.transaction_service import TransactionService

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None

try:
    import pypdf
except ImportError:
    pypdf = None

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


def extract_and_redact_pdf_text(
    pdf_bytes: bytes,
    max_pages: int = 20,
    known_names: list[str] | None = None
) -> tuple[str, bool]:
    """
    Extracts text from PDF up to max_pages and redacts sensitive PII (IBAN, card numbers, IIN, counterparty names).
    Returns (cleaned_text, is_empty_or_scanned).
    """
    if not pypdf:
        return "", True

    try:
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        pages = reader.pages[:max_pages]
        text_content = "\n".join(page.extract_text() or "" for page in pages).strip()
        if not text_content or len(text_content) < 40:
            return "", True

        # Redact IBAN
        text_content = re.sub(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b", "[IBAN_MASKED]", text_content)
        # Redact Card numbers (13-19 digits with optional spaces/dashes)
        text_content = re.sub(r"\b(?:\d[ -]*?){13,19}\b", "[CARD_MASKED]", text_content)
        # Redact IIN/BIN (12 digits)
        text_content = re.sub(r"\b\d{12}\b", "[ID_MASKED]", text_content)
        # Redact P2P transfer counterparty full names
        text_content = re.sub(r"(?:перевод\s+(?:от|кому|клиенту)?\s*)([А-ЯЁ][а-яё]+\s+[А-ЯЁ]\.\s*[А-ЯЁ]\.?)", r"Перевод [ИМЯ_СКРЫТО]", text_content, flags=re.IGNORECASE)

        # Apply PIIGuardrailService mask if available
        try:
            from src.services.pii_guardrail import PIIGuardrailService
            text_content, _ = PIIGuardrailService.mask_text(text_content, known_names=known_names)
        except Exception:
            pass

        return text_content, False
    except Exception as exc:
        logger.warning("Local PDF extraction failed: %s", exc)
        return "", True


class BankStatementService:
    def __init__(self, session: AsyncSession, api_key: str | None = None, model_name: str | None = None):
        self.session = session
        self.api_key = api_key or settings.google_token
        self.client = genai.Client(api_key=self.api_key) if (self.api_key and genai is not None) else None
        self.model_name = model_name or settings.gemini_model

    async def parse_single_pdf(
        self,
        pdf_bytes: bytes,
        filename: str,
        user_id: int | None = None,
        known_names: list[str] | None = None
    ) -> dict[str, Any]:
        """Parse one bank statement PDF using Gemini."""
        if user_id is not None:
            from src.core.rate_limiter import ai_rate_limiter
            allowed, _ = ai_rate_limiter.check_and_record(user_id)
            if not allowed:
                return {"error": "Превышен лимит запросов к AI. Подождите немного.", "transactions": []}

        if not self.client:
            logger.error("Gemini client not initialized for BankStatementService")
            return {"error": "AI service unavailable", "transactions": []}

        # 5 MB file size limit
        if len(pdf_bytes) > 5 * 1024 * 1024:
            return {"error": "Размер файла превышает лимит 5 МБ", "transactions": []}

        extracted_text, is_scanned = extract_and_redact_pdf_text(pdf_bytes, max_pages=20, known_names=known_names)

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
            "2. Исключи внутренние переводы между своими счетами/депозитами внутри одного банка, если они дублируют операции.\n"
            "3. Извлеки метаданные выписки:\n"
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
            if not is_scanned and extracted_text:
                contents = [prompt, f"ТЕКСТ ВЫПИСКИ (PII ОБЕЗЛИЧЕНО):\n{extracted_text[:35000]}"]
            else:
                pdf_part = types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf")
                contents = [prompt, pdf_part]

            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=self.model_name,
                contents=contents,
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

        # Limit to max 3 files per upload
        files = files[:3]

        # Fetch existing categories safely
        cat_service = CategoryService(self.session)
        if hasattr(cat_service, "get_categories") and callable(getattr(cat_service, "get_categories")):
            res = cat_service.get_categories(user_id=user.id)
            categories = await res if asyncio.iscoroutine(res) or hasattr(res, "__await__") else res
        elif hasattr(cat_service, "get_all_categories") and callable(getattr(cat_service, "get_all_categories")):
            res = cat_service.get_all_categories()
            categories = await res if asyncio.iscoroutine(res) or hasattr(res, "__await__") else res
        else:
            categories = []
        if categories is None:
            categories = []
        cat_map: dict[tuple[str, str], Category] = {
            (c.name.lower(), c.type.value if hasattr(c.type, 'value') else str(c.type)): c
            for c in categories
        }
        cat_by_name: dict[str, Category] = {c.name.lower(): c for c in categories}
        default_expense_cat = cat_by_name.get("прочее") or (categories[0] if categories else None)
        default_income_cat = cat_by_name.get("зарплата") or cat_by_name.get("доход") or default_expense_cat

        # Pre-fetch existing statement transactions to deduplicate across re-uploads
        existing_keys: set[tuple] = set()
        try:
            db_res = await self.session.execute(
                select(Transaction.transaction_date, Transaction.amount, Transaction.type, Transaction.item_name)
                .where(Transaction.user_id == user.id, Transaction.source == TransactionSource.statement)
            )
            raw_all = db_res.all() if hasattr(db_res, "all") else []
            if asyncio.iscoroutine(raw_all):
                raw_all = await raw_all
            if isinstance(raw_all, (list, tuple, set)):
                existing_keys = {
                    (tx[0].date() if tx[0] else None, tx[1], tx[2], (tx[3] or "")[:30].strip().lower())
                    for tx in raw_all
                    if isinstance(tx, (tuple, list)) and len(tx) >= 4
                }
        except Exception as e:
            logger.warning("Could not pre-fetch existing statement transactions: %s", e)

        all_tx_records: list[dict[str, Any]] = []
        bank_names: set[str] = set()
        detected_currencies: list[str] = []
        latest_closing_balance: float | None = None
        latest_statement_date: datetime | None = None
        earliest_statement_date: datetime | None = None

        seen_batch: set[tuple] = set()

        known = [user.first_name] if user.first_name else None
        for filename, pdf_bytes in files:
            statement_data = await self.parse_single_pdf(pdf_bytes, filename, user_id=user.id, known_names=known)
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

                tx_type = CategoryType.income if tx.get("type") == "income" else CategoryType.expense
                item_name = str(tx.get("item_name") or "Операция по выписке").strip()[:200]
                amount_dec = Decimal(str(num_amt))

                # Batch & DB Deduplication
                dedup_key = (tx_date.date(), amount_dec, tx_type, item_name[:30].lower())
                if dedup_key in seen_batch or dedup_key in existing_keys:
                    continue
                seen_batch.add(dedup_key)

                all_tx_records.append({
                    "date": tx_date,
                    "amount": amount_dec,
                    "type": tx_type,
                    "item_name": item_name,
                    "category": str(tx.get("category") or "").strip(),
                })

        if not all_tx_records:
            return {
                "success": False,
                "error": "Не удалось обнаружить новые операции в загруженных выписках.",
                "total_count": 0,
            }

        # Sort transactions chronologically
        all_tx_records.sort(key=lambda x: x["date"])

        # Determine start/end of period from actual transactions if metadata missing
        if earliest_statement_date is None:
            earliest_statement_date = all_tx_records[0]["date"]
        if latest_statement_date is None:
            latest_statement_date = all_tx_records[-1]["date"]

        # Insert transactions into database with naive UTC datetime and source=statement
        total_period_expense = Decimal("0")
        total_period_income = Decimal("0")

        for item in all_tx_records:
            cat_name = item["category"].lower()
            type_str = item["type"].value if hasattr(item["type"], 'value') else str(item["type"])
            matched_cat = cat_map.get((cat_name, type_str)) or cat_by_name.get(cat_name)
            if not matched_cat:
                matched_cat = default_income_cat if item["type"] == CategoryType.income else default_expense_cat

            naive_dt = item["date"].replace(tzinfo=None) if item["date"].tzinfo else item["date"]

            tx_obj = Transaction(
                user_id=user.id,
                family_group_id=user.family_group_id,
                category_id=matched_cat.id if matched_cat else 1,
                amount=item["amount"],
                type=item["type"],
                item_name=item["item_name"],
                transaction_date=naive_dt,
                created_at=naive_dt,
                source=TransactionSource.statement,
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
            "currency": user.currency or "KZT",
        }
