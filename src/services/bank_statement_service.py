from __future__ import annotations

import asyncio
import gc
import io
import json
import logging
import re
from collections.abc import Awaitable, Callable
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

CATEGORY_ALIASES: dict[str, str] = {
    "кафе и рестораны": "еда вне дома",
    "рестораны и кафе": "еда вне дома",
    "фастфуд": "еда вне дома",
    "коммунальные услуги": "обязательные расходы",
    "связь": "обязательные расходы",
    "интернет и связь": "обязательные расходы",
    "аренда": "обязательные расходы",
    "супермаркеты": "продукты",
    "аптека": "здоровье",
    "такси": "транспорт",
}


def clean_gemini_json(raw_text: str) -> dict[str, Any]:
    """Strip markdown codeblocks and parse JSON safely, salvaging truncated transaction arrays."""
    text = raw_text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE).strip()
    try:
        return json.loads(text)
    except Exception:
        # Salvage truncated JSON response by recovering all complete {"date": ...} objects
        tx_matches = re.findall(r"\{[^{}]*\"amount\"\s*:[^{}]*\}", text)
        salvaged_txs = []
        for m in tx_matches:
            try:
                salvaged_txs.append(json.loads(m))
            except Exception:
                continue
        if salvaged_txs:
            bank_m = re.search(r'"bank_name"\s*:\s*"([^"]+)"', text)
            curr_m = re.search(r'"currency"\s*:\s*"([^"]+)"', text)
            cb_m = re.search(r'"closing_balance"\s*:\s*(-?\d+(?:\.\d+)?)', text)
            return {
                "bank_name": bank_m.group(1) if bank_m else None,
                "currency": curr_m.group(1) if curr_m else "KZT",
                "closing_balance": float(cb_m.group(1)) if cb_m else None,
                "transactions": salvaged_txs,
            }
        logger.warning("Failed to decode JSON from Gemini (len=%d)", len(raw_text))
        return {}


def _redact_pii(text_content: str, known_names: list[str] | None = None) -> str:
    """Redact IBAN, card numbers, IIN/BIN, counterparty names, and known user names."""
    text_content = re.sub(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b", "[IBAN_MASKED]", text_content)
    text_content = re.sub(r"\b(?:\d[ -]*?){13,19}\b", "[CARD_MASKED]", text_content)
    text_content = re.sub(r"\b\d{12}\b", "[ID_MASKED]", text_content)
    text_content = re.sub(
        r"(?:перевод\s+(?:от|кому|клиенту)?\s*)([А-ЯЁA-Z][а-яёa-z]+\s+[А-ЯЁA-Z]\.(?:\s*[А-ЯЁA-Z]\.?)?)",
        r"Перевод [ИМЯ_СКРЫТО]",
        text_content,
        flags=re.IGNORECASE,
    )
    try:
        from src.services.pii_guardrail_service import PIIGuardrailService
        text_content = PIIGuardrailService.mask_text(text_content, known_names=known_names)
    except Exception:
        pass
    return text_content


def extract_and_redact_pdf_chunks(
    pdf_bytes: bytes,
    max_pages: int = 150,
    chars_per_chunk: int = 14000,
    known_names: list[str] | None = None,
) -> tuple[list[str], bool]:
    """
    Extracts text from up to max_pages of a PDF, redacts PII, and splits into manageable chunks
    so full 1-year statements are parsed completely without hitting Gemini output token limits.
    """
    if not pypdf:
        return [], True

    try:
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        pages = reader.pages[:max_pages]
        chunks: list[str] = []
        current_chunk: list[str] = []
        current_len = 0

        for idx, page in enumerate(pages, start=1):
            page_text = (page.extract_text() or "").strip()
            if not page_text:
                continue
            redacted_page = f"--- СТРАНИЦА {idx} ---\n" + _redact_pii(page_text, known_names=known_names)
            if current_len + len(redacted_page) > chars_per_chunk and current_chunk:
                chunks.append("\n\n".join(current_chunk))
                current_chunk = [redacted_page]
                current_len = len(redacted_page)
            else:
                current_chunk.append(redacted_page)
                current_len += len(redacted_page)

        if current_chunk:
            chunks.append("\n\n".join(current_chunk))

        total_chars = sum(len(c) for c in chunks)
        if not chunks or total_chars < 40:
            return [], True

        return chunks, False
    except Exception as exc:
        logger.warning("Local PDF extraction failed: %s", exc)
        return [], True


def extract_and_redact_pdf_text(
    pdf_bytes: bytes,
    max_pages: int = 150,
    known_names: list[str] | None = None,
) -> tuple[str, bool]:
    """Backwards-compatible wrapper returning full joined text."""
    chunks, is_scanned = extract_and_redact_pdf_chunks(
        pdf_bytes, max_pages=max_pages, chars_per_chunk=500000, known_names=known_names
    )
    if is_scanned or not chunks:
        return "", True
    return "\n\n".join(chunks), False


STATEMENT_PROMPT = (
    "Ты специализированный финансовый анализатор банковских выписок (PDF) приложения Smart Bujet.\n"
    "Твоя задача — извлечь из предоставленного фрагмента банковской выписки все финансовые операции, "
    "начальный и конечный баланс, валюту счета, банк и период выписки.\n\n"
    "СТРОГИЕ ПРАВИЛА:\n"
    "1. Извлеки все строки операций из текста. Для каждой операции укажи:\n"
    "   - 'date': дата операции в формате 'YYYY-MM-DD' (или 'YYYY-MM-DDTHH:MM:SS').\n"
    "   - 'amount': сумма в виде положительного числа (float/int).\n"
    "   - 'type': 'expense' (списание, покупка, комиссия, исходящий перевод) или 'income' (пополнение, зарплата, входящий перевод, кешбэк, проценты).\n"
    "   - 'item_name': получатель/магазин/описание (например 'Magnum', 'Yandex Go', 'Зарплата', 'Перевод'). Не включай личные ФИО.\n"
    "   - 'category': категория строго из списка: 'Продукты', 'Еда вне дома', 'Ребёнок', 'Транспорт', 'Здоровье', 'Обязательные расходы', 'Питомец', 'Развлечения', 'Образование', 'Подписки', 'Ремонт', 'Шоппинг', 'Зарплата', 'Подарок', 'Денежный перевод', 'Прочее'.\n"
    "2. Исключи внутренние переводы между своими счетами/депозитами внутри одного банка (например, 'На Kaspi Депозит', 'С Kaspi Депозита').\n"
    "3. Извлеки метаданные выписки (если они видны в этом фрагменте, иначе null):\n"
    "   - 'bank_name': название банка (например 'Kaspi Bank', 'Halyk Bank', 'ForteBank', 'Сбербанк', 'Тинькофф').\n"
    "   - 'currency': валюта ('KZT', 'USD', 'RUB', 'EUR'). По умолчанию 'KZT'.\n"
    "   - 'period_start': дата начала выписки 'YYYY-MM-DD' или null.\n"
    "   - 'period_end': дата конца выписки 'YYYY-MM-DD' или null.\n"
    "   - 'starting_balance': начальный остаток (float или null).\n"
    "   - 'closing_balance': итоговый остаток на конец периода / исходящий остаток (float или null).\n\n"
    "Верни СТРОГО валидный JSON:\n"
    "{\n"
    '  "bank_name": "Kaspi Bank",\n'
    '  "currency": "KZT",\n'
    '  "period_start": "2025-01-01",\n'
    '  "period_end": "2025-12-31",\n'
    '  "starting_balance": 50000.0,\n'
    '  "closing_balance": 125000.0,\n'
    '  "transactions": [\n'
    '    {"date": "2025-01-05", "amount": 3200.0, "type": "expense", "item_name": "Magnum", "category": "Продукты"}\n'
    "  ]\n"
    "}"
)


class BankStatementService:
    def __init__(self, session: AsyncSession, api_key: str | None = None, model_name: str | None = None):
        self.session = session
        self.api_key = api_key or settings.google_token
        self.client = genai.Client(api_key=self.api_key) if (self.api_key and genai is not None) else None
        self.model_name = model_name or settings.gemini_model

    async def _call_gemini_chunk(self, contents: list[Any]) -> dict[str, Any]:
        """Call Gemini for a single chunk/document with JSON mime type config."""
        cfg = (
            types.GenerateContentConfig(response_mime_type="application/json", temperature=0.1)
            if types is not None and hasattr(types, "GenerateContentConfig")
            else None
        )
        kwargs: dict[str, Any] = {"model": self.model_name, "contents": contents}
        if cfg is not None:
            kwargs["config"] = cfg

        response = await asyncio.to_thread(self.client.models.generate_content, **kwargs)
        raw_text = response.text or ""
        parsed = clean_gemini_json(raw_text)
        return parsed if isinstance(parsed, dict) else {}

    async def parse_single_pdf(
        self,
        pdf_bytes: bytes,
        filename: str,
        user_id: int | None = None,
        known_names: list[str] | None = None,
        progress_callback: Callable[[int, int], Awaitable[None]] | None = None,
    ) -> dict[str, Any]:
        """Parse one bank statement PDF (supporting multi-page 1-year statements via chunking)."""
        if user_id is not None:
            from src.services.ai_service import ai_rate_limiter
            allowed, reason = ai_rate_limiter.check_and_record(user_id)
            if not allowed:
                return {"error": reason or "Превышен лимит запросов к AI. Подождите немного.", "transactions": []}

        if not self.client:
            logger.error("Gemini client not initialized for BankStatementService")
            return {"error": "AI service unavailable", "transactions": []}

        # 15 MB file size limit for yearly statements
        if len(pdf_bytes) > 15 * 1024 * 1024:
            return {"error": "Размер файла превышает лимит 15 МБ", "transactions": []}

        chunks, is_scanned = extract_and_redact_pdf_chunks(
            pdf_bytes, max_pages=150, chars_per_chunk=14000, known_names=known_names
        )

        try:
            if is_scanned or not chunks:
                pdf_part = types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf")
                parsed = await self._call_gemini_chunk([STATEMENT_PROMPT, pdf_part])
                return parsed or {"error": "Invalid response format", "transactions": []}

            total_chunks = len(chunks)
            merged: dict[str, Any] = {
                "bank_name": None,
                "currency": None,
                "period_start": None,
                "period_end": None,
                "starting_balance": None,
                "closing_balance": None,
                "transactions": [],
            }

            sem = asyncio.Semaphore(2)
            completed_chunks = 0

            async def process_chunk(idx: int, chunk_text: str) -> tuple[int, dict[str, Any]]:
                nonlocal completed_chunks
                async with sem:
                    res = await self._call_gemini_chunk(
                        [
                            STATEMENT_PROMPT,
                            f"ФРАГМЕНТ ВЫПИСКИ ({idx + 1} из {total_chunks}, PII ОБЕЗЛИЧЕНО):\n{chunk_text}",
                        ]
                    )
                    completed_chunks += 1
                    if progress_callback:
                        try:
                            await progress_callback(completed_chunks, total_chunks)
                        except Exception:
                            pass
                    return idx, res

            tasks = [process_chunk(i, c) for i, c in enumerate(chunks)]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for item in sorted(
                (r for r in results if isinstance(r, tuple)), key=lambda x: x[0]
            ):
                _, chunk_data = item
                if not isinstance(chunk_data, dict):
                    continue
                if not merged["bank_name"] and chunk_data.get("bank_name"):
                    merged["bank_name"] = chunk_data["bank_name"]
                if not merged["currency"] and chunk_data.get("currency"):
                    merged["currency"] = chunk_data["currency"]
                if not merged["period_start"] and chunk_data.get("period_start"):
                    merged["period_start"] = chunk_data["period_start"]
                if chunk_data.get("period_end"):
                    if not merged["period_end"] or str(chunk_data["period_end"]) > str(merged["period_end"]):
                        merged["period_end"] = chunk_data["period_end"]
                if merged["starting_balance"] is None and chunk_data.get("starting_balance") is not None:
                    merged["starting_balance"] = chunk_data["starting_balance"]
                if merged["closing_balance"] is None and chunk_data.get("closing_balance") is not None:
                    merged["closing_balance"] = chunk_data["closing_balance"]

                txs = chunk_data.get("transactions")
                if isinstance(txs, list):
                    merged["transactions"].extend(txs)

            return merged
        except Exception as exc:
            logger.error("Failed to parse PDF statement '%s': %s", filename, exc)
            return {"error": str(exc), "transactions": []}

    async def import_statements(
        self,
        user_id: int,
        files: list[tuple[str, bytes]],
        progress_callback: Callable[[str], Awaitable[None]] | None = None,
    ) -> dict[str, Any]:
        """
        Process one or multiple PDF bank statements for the user,
        persist transactions, calibrate initial balance to match closing balance,
        and return summary stats.
        """
        user = await self.session.get(User, user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")

        files = files[:3]

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
            (c.name.lower(), c.type.value if hasattr(c.type, "value") else str(c.type)): c
            for c in categories
        }
        cat_by_name: dict[str, Category] = {c.name.lower(): c for c in categories}
        default_expense_cat = cat_by_name.get("прочее") or (categories[0] if categories else None)
        default_income_cat = cat_by_name.get("зарплата") or cat_by_name.get("доход") or default_expense_cat

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
        total_files = len(files)

        for file_idx, (filename, pdf_bytes) in enumerate(files, start=1):
            async def on_chunk_progress(done_chunks: int, total_chunks: int, f_idx: int = file_idx) -> None:
                if progress_callback and total_chunks > 1:
                    await progress_callback(
                        f"⏳ <b>Обрабатываю выписку {f_idx} из {total_files}...</b>\n"
                        f"Проанализировано фрагментов: <b>{done_chunks} из {total_chunks}</b>"
                    )

            parse_kwargs: dict[str, Any] = {
                "user_id": user.id,
                "known_names": known,
            }
            if progress_callback is not None:
                parse_kwargs["progress_callback"] = on_chunk_progress

            statement_data = await self.parse_single_pdf(pdf_bytes, filename, **parse_kwargs)
            gc.collect()

            bank = statement_data.get("bank_name")
            if bank:
                bank_names.add(bank)

            currency = statement_data.get("currency")
            if currency:
                detected_currencies.append(currency.upper())

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
            elif latest_closing_balance is None and statement_data.get("closing_balance") is not None:
                try:
                    latest_closing_balance = float(statement_data["closing_balance"])
                except Exception:
                    pass

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
                amount_dec = Decimal(str(round(num_amt, 2)))

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

        all_tx_records.sort(key=lambda x: x["date"])

        if earliest_statement_date is None:
            earliest_statement_date = all_tx_records[0]["date"]
        if latest_statement_date is None:
            latest_statement_date = all_tx_records[-1]["date"]

        total_period_expense = Decimal("0")
        total_period_income = Decimal("0")

        for item in all_tx_records:
            raw_cat = item["category"].lower()
            cat_name = CATEGORY_ALIASES.get(raw_cat, raw_cat)
            type_str = item["type"].value if hasattr(item["type"], "value") else str(item["type"])
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

        if detected_currencies:
            user.currency = detected_currencies[0]

        net_cashflow = total_period_income - total_period_expense
        if latest_closing_balance is not None:
            calculated_initial = Decimal(str(latest_closing_balance)) - net_cashflow
            user.initial_balance = max(Decimal("0.0"), calculated_initial)
        elif user.initial_balance is None:
            user.initial_balance = Decimal("0.0")

        await self.session.commit()

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
