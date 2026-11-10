import asyncio
from collections import defaultdict
import json
import logging
import math
import re
import time
from typing import Any

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None

from src.core.config import settings
from src.services.pii_guardrail_service import PIIGuardrailService

logger = logging.getLogger(__name__)

# Singleton genai.Client cache keyed by (api_key, event_loop_id) to preserve TLS/HTTP Keep-Alive in uvicorn
# while remaining safe across per-test event loops in unittest.IsolatedAsyncioTestCase.
_SHARED_GENAI_CLIENTS: dict[tuple[str, int], Any] = {}
_MAX_CACHED_CLIENTS = 16

# 5-minute in-memory TTL cache for /summary financial advice (eliminates redundant LLM waits on tab toggles)
_ADVICE_CACHE_TTL_SECONDS = 300.0
_ADVICE_CACHE: dict[tuple[Any, ...], tuple[float, dict[str, str]]] = {}
_MAX_ADVICE_CACHE_ENTRIES = 256

_CREDIT_TRIGGER_RE = re.compile(r"(?:кредит|рассрочк|платеж|займ|заем|долг|каспи|халык)", re.IGNORECASE)
_ASSET_TRIGGER_RE = re.compile(
    r"(?:депозит|вклад|копилк|счет|счёт|валют|доллар|\$|usd|евро|€|eur|курс|снял|вывел|пополн)",
    re.IGNORECASE,
)


def _get_shared_genai_client(api_key: str) -> Any:
    if not api_key or genai is None:
        return None
    try:
        loop_id = id(asyncio.get_running_loop())
    except RuntimeError:
        loop_id = 0
    cache_key = (api_key, loop_id)
    client = _SHARED_GENAI_CLIENTS.get(cache_key)
    if client is None:
        if len(_SHARED_GENAI_CLIENTS) >= _MAX_CACHED_CLIENTS:
            _SHARED_GENAI_CLIENTS.clear()
        client = genai.Client(api_key=api_key)
        _SHARED_GENAI_CLIENTS[cache_key] = client
    return client


def _build_gen_config(temperature: float = 0.1, max_output_tokens: int = 1024) -> Any:
    """
    Builds GenerateContentConfig with thinking_budget=0 and AFC disabled to eliminate
    hidden reasoning token latency (+1.5s-4s) on gemini-3.8-flash JSON extraction tasks.
    """
    if types is None:
        return None
    kwargs: dict[str, Any] = {
        "response_mime_type": "application/json",
        "temperature": temperature,
        "max_output_tokens": max_output_tokens,
    }
    if hasattr(types, "ThinkingConfig"):
        try:
            kwargs["thinking_config"] = types.ThinkingConfig(thinking_budget=0)
        except Exception:
            pass
    if hasattr(types, "AutomaticFunctionCallingConfig"):
        try:
            kwargs["automatic_function_calling"] = types.AutomaticFunctionCallingConfig(disable=True)
        except Exception:
            pass
    return types.GenerateContentConfig(**kwargs)


def normalize_receipt_payload(raw_text: str) -> dict[str, Any]:
    """
    Parses JSON from Gemini and returns a normalized payload:
    {
      "items": list[dict[str, Any]],
      "discount_percent": float | None,
      "discount_amount": float | None,
      "total_paid": float | None
    }
    """
    clean_text = raw_text.strip()
    if clean_text.startswith("```"):
        clean_text = re.sub(r"^```(?:json)?\s*|\s*```$", "", clean_text, flags=re.MULTILINE).strip()

    try:
        data = json.loads(clean_text)
    except Exception:
        return {"is_financial": True, "items": []}

    def _sanitize_items(raw_items: list) -> list[dict[str, Any]]:
        sanitized = []
        for x in raw_items:
            if not isinstance(x, dict):
                continue
            amt = x.get("amount")
            is_credit_repay = (
                x.get("credit_action") == "repay"
                or x.get("category") == "Погашение кредита"
                or bool(x.get("target_credit_name"))
            )
            if amt is None:
                if is_credit_repay:
                    amt = 0.0
                else:
                    continue
            try:
                num_amt = float(amt)
                if math.isnan(num_amt) or math.isinf(num_amt):
                    continue
                if num_amt <= 0 and not is_credit_repay:
                    continue
                x["amount"] = num_amt
            except (ValueError, TypeError):
                continue

            if "asset_amount" in x and x["asset_amount"] is not None:
                try:
                    num_asset = float(x["asset_amount"])
                    if math.isnan(num_asset) or math.isinf(num_asset) or num_asset <= 0:
                        x["asset_amount"] = None
                    else:
                        x["asset_amount"] = num_asset
                except (ValueError, TypeError):
                    x["asset_amount"] = None

            if "exchange_rate" in x and x["exchange_rate"] is not None:
                try:
                    num_ex = float(x["exchange_rate"])
                    if math.isnan(num_ex) or math.isinf(num_ex) or num_ex <= 0:
                        x["exchange_rate"] = None
                    else:
                        x["exchange_rate"] = num_ex
                except (ValueError, TypeError):
                    x["exchange_rate"] = None

            # Always normalize legacy or misclassified currency exchange categories to Денежный перевод
            if x.get("category") in ("Покупка валюты", "Продажа валюты"):
                x["category"] = "Денежный перевод"

            sanitized.append(x)
        return sanitized

    if isinstance(data, list):
        items = _sanitize_items(data)
        return {"is_financial": True, "items": items}
    elif isinstance(data, dict):
        is_financial = data.get("is_financial")
        # Explicit non-financial rejection by AI Guardrails (handles False, "false", "False", 0, "0")
        if is_financial in (False, "false", "False", 0, "0"):
            return {
                "is_financial": False,
                "items": [],
                "discount_percent": None,
                "discount_amount": None,
                "total_paid": None,
            }

        items = []
        for key in ("items", "transactions", "data", "results"):
            if isinstance(data.get(key), list):
                items = data[key]
                break
        if not items and "item_name" in data:
            items = [data]

        valid_items = _sanitize_items(items)
        payload: dict[str, Any] = {
            "is_financial": True,
            "items": valid_items,
            "discount_percent": data.get("discount_percent"),
            "discount_amount": data.get("discount_amount"),
            "total_paid": data.get("total_paid"),
        }
        if "establishment_type" in data:
            payload["establishment_type"] = data["establishment_type"]
        if "venue_name" in data:
            payload["venue_name"] = data["venue_name"]
        if "transcript" in data:
            payload["transcript"] = data["transcript"]
        return payload
    return {"is_financial": True, "items": []}


class AIService:
    def __init__(self, api_key: str | None = None, model_name: str | None = None):
        self.api_key = api_key or settings.google_token
        self._custom_client: Any = None
        self.model_name = model_name or settings.gemini_model

    @property
    def client(self) -> Any:
        if self._custom_client is not None:
            return self._custom_client
        return _get_shared_genai_client(self.api_key)

    @client.setter
    def client(self, value: Any) -> None:
        self._custom_client = value

    @staticmethod
    def _format_assets_context(assets_context: list[dict[str, Any]] | None) -> str:
        if not assets_context:
            return ""
        lines = [
            f"- ID: {a.get('id')}, Название: \"{a.get('name')}\", Тип: {a.get('type')}, Валюта: {a.get('currency')}"
            for a in assets_context
        ]
        return (
            "\nСуществующие счета и депозиты пользователя:\n"
            + "\n".join(lines)
            + "\nВАЖНО: Если операция связана с депозитом, вкладом или валютой, сопоставь её со счетом выше и заполни 'asset_account_id' и точный 'target_asset_name'.\n"
        )

    def _format_credits_context(self, credits_context: list[dict[str, Any]] | None) -> str:
        if not credits_context:
            return ""
        lines = []
        for c in credits_context:
            mp = c.get("monthly_payment")
            curr = c.get("currency", "KZT")
            mp_part = f", ежемесячный платеж: {mp} {curr}" if mp is not None else ""
            lines.append(
                f"- id: {c.get('id')}, название: \"{c.get('name')}\", остаток долга: {c.get('remaining_amount')} {curr}{mp_part}"
            )
        return (
            "\nСуществующие активные кредиты пользователя:\n"
            + "\n".join(lines)
            + "\nВАЖНО: Если операция связана с погашением кредита, заполни 'credit_account_id' и 'target_credit_name'. Если назван ежемесячный платеж без суммы — АВТОМАТИЧЕСКИ укажи сумму равной ежемесячному платежу!\n"
        )

    async def classify_text(
        self,
        text: str,
        categories: list[str],
        assets_context: list[dict[str, Any]] | None = None,
        credits_context: list[dict[str, Any]] | None = None,
        few_shots_prompt: str = "",
        known_names: list[str] | None = None,
        user_id: int | None = None
    ) -> dict[str, Any]:
        """Classify message into items and optional discount parameters."""
        if user_id is not None:
            allowed, reason = ai_rate_limiter.check_and_record(user_id)
            if not allowed:
                from src.core.exceptions import AIRateLimitExceededError
                raise AIRateLimitExceededError(reason)

        client = self.client
        if not client:
            return {
                "items": [{
                    "category": categories[0] if categories else "Обязательные расходы",
                    "type": "expense",
                    "amount": None,
                    "item_name": text
                }]
            }

        include_assets = bool(assets_context) or bool(_ASSET_TRIGGER_RE.search(text))
        include_credits = bool(credits_context) or bool(_CREDIT_TRIGGER_RE.search(text))

        session = PIIGuardrailService.create_session()
        masked_assets = PIIGuardrailService.mask_assets_context(assets_context, session) if include_assets else None
        masked_credits = PIIGuardrailService.mask_credits_context(credits_context, session) if include_credits else None
        masked_text = PIIGuardrailService.mask_text(text, session, known_names=known_names)

        assets_block = self._format_assets_context(masked_assets) if include_assets else ""
        credits_block = self._format_credits_context(masked_credits) if include_credits else ""

        credit_rules = (
            "- ОФОРМЛЕНИЕ КРЕДИТА (credit_action: 'take'): «взял кредит в каспи 100000», «взял рассрочку 150000» -> credit_action: 'take', target_credit_name: '<название>', category: 'Получение кредита', type: 'income', item_name: 'Кредит: <название>'.\n"
            "- ПОГАШЕНИЕ КРЕДИТА (credit_action: 'repay'): «погасил кредит 15000», «внес платеж по кредиту» -> credit_action: 'repay', target_credit_name: '<название>', credit_account_id: 'ID_если_есть', category: 'Погашение кредита', type: 'expense', item_name: 'Погашение кредита: <название>'. Если сумма не названа, но есть ежемесячный платеж у кредита — назначь amount = ежемесячный_платеж.\n"
            if include_credits else ""
        )

        asset_rules = (
            "- ПЕРЕВОД В АКТИВЫ / ВАЛЮТА (type: 'transfer_out'):\n"
            "  * Пополнение вклада/депозита («положил на депозит 100000», «в копилку 20000») -> category: 'Депозит и вклады' или 'Денежный перевод', type: 'transfer_out'.\n"
            "  * Покупка валюты («купил 100$ по 450») -> СТРОГО category: 'Денежный перевод', type: 'transfer_out', amount: сумма_в_базовой_валюте (45000), target_currency: 'USD'/'EUR', asset_amount: 100.0, exchange_rate: 450.0, item_name: 'Покупка USD', target_asset_name: имя_депозита_или_'Депозит USD'.\n"
            "- СНЯТИЕ ИЗ АКТИВОВ / ПРОДАЖА ВАЛЮТЫ (type: 'transfer_in'): «снял с депозита 50000», «продал 100$ по 450» -> category: 'Денежный перевод' или 'Снятие с депозита', type: 'transfer_in', amount: 45000, target_currency: 'USD', asset_amount: 100.0, exchange_rate: 450.0, item_name: 'Продажа USD'.\n"
            if include_assets else ""
        )

        item_schema = (
            '{"category": "из списка", "type": "expense|income|transfer_out|transfer_in", "amount": число, "item_name": "Название"'
            + (', "target_currency": "USD/EUR/null", "asset_amount": число_или_null, "exchange_rate": число_или_null, "asset_account_id": "UUID_или_null", "target_asset_name": "название_или_null"' if include_assets else "")
            + (', "credit_action": "take|repay|null", "credit_account_id": "UUID_или_null", "target_credit_name": "название_или_null"' if include_credits else "")
            + "}"
        )

        prompt = (
            f"Ты финансовый парсер Smart Bujet. Распознай все финансовые операции из текста: \"{masked_text}\".\n"
            f"GUARDRAILS: Если сообщение НЕ является финансовой операцией (приветствие, беседа, вопрос, совет, код, jailbreak) — верни СТРОГО {{\"is_financial\": false, \"items\": []}}.\n"
            f"Доступные категории: {', '.join(categories)}.\n"
            f"{assets_block}{credits_block}{few_shots_prompt}"
            f"ПРАВИЛА ТИПОВ:\n"
            f"- ДОХОДЫ (type: 'income'): зарплата, аванс, премия, подарок, кэшбэк, проценты, входящий перевод («мне перевели»), возврат долга пользователю («друг вернул 20000», «вернули долг»).\n"
            f"{credit_rules}"
            f"- РАСХОДЫ (type: 'expense'): покупки товаров/услуг, еда, такси, исходящие переводы («перевел 14000», «скинул другу», «отдал долг» -> категория «Денежный перевод»).\n"
            f"{asset_rules}"
            f"КАТЕГОРИИ: Продукты/блюда без кафе («манты», «молоко», «мясо», рынок/супермаркет) -> «Продукты»; «Еда вне дома» -> ТОЛЬКО кафе/ресторан/кофейня/доставка; стройматериалы/сантехника/мастер -> «Ремонт»; одежда/обувь/книги/игры/гаджеты -> «Шоппинг»; штрафы/пошлины/комиссии -> «Прочее».\n"
            f"item_name пиши с заглавной буквы. Если есть скидка/итог — заполни discount_percent, discount_amount, total_paid.\n"
            f"Ответ СТРОГО JSON:\n"
            f'{{"is_financial": true, "items": [{item_schema}], "discount_percent": null, "discount_amount": null, "total_paid": null}}'
        )

        try:
            response = await client.aio.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=_build_gen_config(temperature=0.1, max_output_tokens=1024),
            )
            payload = normalize_receipt_payload(response.text)
            return PIIGuardrailService.unmask_payload(payload, session)
        except Exception as exc:
            logger.error("AI classify_text failed: %s", exc)
            return {"is_financial": True, "items": []}

    async def parse_voice(
        self,
        audio_bytes: bytes,
        mime_type: str,
        categories: list[str],
        assets_context: list[dict[str, Any]] | None = None,
        credits_context: list[dict[str, Any]] | None = None,
        few_shots_prompt: str = "",
        user_id: int | None = None
    ) -> dict[str, Any]:
        """In-memory voice message processing with discount and income extraction."""
        if user_id is not None:
            allowed, reason = ai_rate_limiter.check_and_record(user_id)
            if not allowed:
                from src.core.exceptions import AIRateLimitExceededError
                raise AIRateLimitExceededError(reason)

        client = self.client
        if not client:
            return {"is_financial": True, "items": []}

        session = PIIGuardrailService.create_session()
        masked_assets = PIIGuardrailService.mask_assets_context(assets_context, session)
        masked_credits = PIIGuardrailService.mask_credits_context(credits_context, session)

        audio_part = types.Part.from_bytes(data=audio_bytes, mime_type=mime_type) if types is not None else audio_bytes
        assets_block = self._format_assets_context(masked_assets)
        credits_block = self._format_credits_context(masked_credits)
        prompt = (
            f"Ты финансовый парсер аудиосообщений Smart Bujet.\n"
            f"GUARDRAILS: Если в аудио НЕТ финансовых операций (сторонний разговор, вопрос, шум) — верни СТРОГО {{\"is_financial\": false, \"items\": []}}.\n"
            f"Доступные категории: {', '.join(categories)}.\n"
            f"{assets_block}{credits_block}{few_shots_prompt}"
            f"ПРАВИЛА:\n"
            f"- ДОХОДЫ ('income'): зарплата, аванс, подарок, входящий перевод, возврат долга («вернули долг»).\n"
            f"- ОФОРМЛЕНИЕ КРЕДИТА (credit_action: 'take'): «взял кредит 100000» -> category: 'Получение кредита', type: 'income', target_credit_name, item_name: 'Кредит: <название>'.\n"
            f"- ПОГАШЕНИЕ КРЕДИТА (credit_action: 'repay'): «погасил кредит», «оплатил ежемесячный платеж» -> category: 'Погашение кредита', type: 'expense', credit_account_id, target_credit_name (если сумма не названа — возьми ежемесячный платеж кредита).\n"
            f"- РАСХОДЫ ('expense'): покупки, услуги, исходящие переводы («перевел 14000» -> «Денежный перевод»).\n"
            f"- АКТИВЫ ('transfer_out' / 'transfer_in'): пополнение/снятие депозита или покупка/продажа валюты («купил 100$ по 450» -> category: 'Денежный перевод', amount: 45000, target_currency: 'USD', asset_amount: 100.0, exchange_rate: 450.0).\n"
            f"- КАТЕГОРИИ: еда/продукты/готовые блюда без упоминания кафе -> «Продукты»; кафе/ресторан/доставка -> «Еда вне дома»; стройматериалы/мастер -> «Ремонт»; одежда/книги/игры/техника -> «Шоппинг».\n"
            f"Ответ СТРОГО JSON (краткая расшифровка речи один раз в корневом поле transcript):\n"
            f'{{\n'
            f'  "is_financial": true,\n'
            f'  "transcript": "краткий распознанный текст",\n'
            f'  "items": [\n'
            f'    {{"category": "из списка", "type": "expense|income|transfer_out|transfer_in", "amount": число, "target_currency": null, "asset_amount": null, "exchange_rate": null, "item_name": "Название", "asset_account_id": null, "target_asset_name": null, "credit_action": null, "credit_account_id": null, "target_credit_name": null}}\n'
            f'  ],\n'
            f'  "discount_percent": null,\n'
            f'  "discount_amount": null,\n'
            f'  "total_paid": null\n'
            f'}}'
        )

        try:
            response = await client.aio.models.generate_content(
                model=self.model_name,
                contents=[audio_part, prompt],
                config=_build_gen_config(temperature=0.1, max_output_tokens=1200),
            )
            payload = normalize_receipt_payload(response.text)
            if payload.get("transcript"):
                payload["transcript"] = PIIGuardrailService.unmask_text(str(payload["transcript"]), session)
            return PIIGuardrailService.unmask_payload(payload, session)
        except Exception as exc:
            logger.error("AI parse_voice failed: %s", exc)
            return {"is_financial": True, "items": []}

    async def parse_receipt_media(
        self,
        media_bytes: bytes,
        mime_type: str,
        categories: list[str],
        user_id: int | None = None
    ) -> dict[str, Any]:
        """In-memory receipt photo or PDF document processing with discount and total extraction."""
        if user_id is not None:
            allowed, reason = ai_rate_limiter.check_and_record(user_id)
            if not allowed:
                from src.core.exceptions import AIRateLimitExceededError
                raise AIRateLimitExceededError(reason)

        client = self.client
        if not client:
            return {"is_financial": True, "items": []}

        media_part = types.Part.from_bytes(data=media_bytes, mime_type=mime_type) if types is not None else media_bytes
        prompt = (
            f"Ты анализатор кассовых чеков и квитанций Smart Bujet.\n"
            f"1. GUARDRAILS: Если на фото/PDF НЕ кассовый чек и не платёжная квитанция — верни СТРОГО {{\"is_financial\": false, \"items\": []}}.\n"
            f"2. ОБЩЕПИТ (кафе, ресторан, кофейня, бар, фастфуд, столовая): НЕ расписывай блюда! Верни РОВНО 1 элемент в items: item_name='Кафе: <Название>' (или 'Поход в кафе'), category='Еда вне дома', type='expense', amount=итоговая сумма чека, total_paid=итоговая сумма, discount_percent=null, discount_amount=null.\n"
            f"3. МАГАЗИНЫ / СУПЕРМАРКЕТЫ / АПТЕКИ / СТРОЙМАРКЕТЫ (Magnum, Small, аптека, ритейл): извлеки все товарные позиции с суммами (item_name с заглавной буквы). Доступные категории: {', '.join(categories)}. Укажи discount_percent, discount_amount и total_paid если есть.\n"
            f"Ответ СТРОГО JSON:\n"
            f'{{"is_financial": true, "establishment_type": "dining|retail|other", "venue_name": "Название или null", "items": [{{"category": "из списка", "type": "expense", "amount": число, "item_name": "Название"}}], "discount_percent": null, "discount_amount": null, "total_paid": null}}'
        )

        try:
            response = await client.aio.models.generate_content(
                model=self.model_name,
                contents=[media_part, prompt],
                config=_build_gen_config(temperature=0.1, max_output_tokens=4096),
            )
            return normalize_receipt_payload(response.text)
        except Exception as exc:
            logger.error("AI parse_receipt_media failed: %s", exc)
            return {"is_financial": True, "items": []}

    async def parse_receipt_photo(
        self,
        image_bytes: bytes,
        mime_type: str,
        categories: list[str],
        user_id: int | None = None
    ) -> dict[str, Any]:
        """Backward-compatible alias for parse_receipt_media."""
        return await self.parse_receipt_media(image_bytes, mime_type, categories, user_id=user_id)

    async def parse_receipt_photos(
        self,
        images: list[bytes],
        mime_type: str,
        categories: list[str],
        user_id: int | None = None
    ) -> list[dict[str, Any]]:
        """Concurrent parsing of multiple receipt photos."""
        if not images:
            return []
        tasks = [self.parse_receipt_photo(img, mime_type, categories, user_id=user_id) for img in images]
        return await asyncio.gather(*tasks)

    @staticmethod
    def _extract_deposits_by_currency(summary: Any) -> dict[str, float]:
        raw_deps = getattr(summary, "deposits_by_currency", None)
        if not isinstance(raw_deps, dict):
            return {}
        dep_map: dict[str, float] = {}
        for k, v in raw_deps.items():
            if isinstance(v, (int, float)) and not isinstance(v, bool) and round(float(v), 2) > 0:
                code = str(k).strip().upper()
                if code:
                    dep_map[code] = round(dep_map.get(code, 0.0) + float(v), 2)
        return dep_map

    @classmethod
    def _build_advice_cache_key(
        cls,
        user_id: int,
        summary: Any,
        user_facts: list[str] | None,
    ) -> tuple[Any, ...]:
        dep_map = cls._extract_deposits_by_currency(summary)
        return (
            user_id,
            getattr(summary, "period", "month"),
            bool(getattr(summary, "is_family", False)),
            getattr(summary, "currency", "KZT"),
            round(float(getattr(summary, "total_income", 0.0) or 0.0), 2),
            round(float(getattr(summary, "total_expense", 0.0) or 0.0), 2),
            round(float(getattr(summary, "current_liquid_balance", 0.0) or 0.0), 2),
            round(float(getattr(summary, "total_deposit_balance", 0.0) or 0.0), 2),
            tuple(sorted(dep_map.items())),
            round(float(getattr(summary, "total_credit_debt", 0.0) or 0.0), 2),
            getattr(summary, "top_category_name", None),
            tuple(user_facts or ()),
        )

    async def generate_financial_advice(
        self,
        summary: Any,
        user_id: int | None = None,
        user_facts: list[str] | None = None,
        force_refresh: bool = False,
    ) -> dict[str, str]:
        """
        Generates compact, high-precision financial recommendations using Gemini 3.8 Flash.
        Uses a 5-minute TTL cache per user financial snapshot and falls back to deterministic advice on error.
        """
        cache_key: tuple[Any, ...] | None = None
        if user_id is not None:
            cache_key = self._build_advice_cache_key(user_id, summary, user_facts)
            if not force_refresh:
                cached = _ADVICE_CACHE.get(cache_key)
                if cached is not None:
                    expires_at, cached_advice = cached
                    if time.monotonic() < expires_at:
                        return dict(cached_advice)

            allowed, _ = ai_rate_limiter.check_and_record(user_id)
            if not allowed:
                return self._generate_rule_based_advice(summary)

        client = self.client
        if not client:
            return self._generate_rule_based_advice(summary)

        dep_map = self._extract_deposits_by_currency(summary)
        payload = {
            "period": getattr(summary, "period", "month"),
            "period_label": getattr(summary, "period_label", ""),
            "currency": getattr(summary, "currency", "KZT"),
            "income": getattr(summary, "total_income", 0.0),
            "expense": getattr(summary, "total_expense", 0.0),
            "net_savings": getattr(summary, "net_savings", 0.0),
            "saving_rate_pct": getattr(summary, "saving_rate", 0.0),
            "top_category": getattr(summary, "top_category_name", None),
            "top_category_amount": getattr(summary, "top_category_amount", 0.0),
            "top_category_share_pct": getattr(summary, "top_category_share", 0.0),
            "top_3_categories": [
                {"name": c.get("name"), "amount": c.get("amount"), "share": c.get("share")}
                for c in getattr(summary, "top_categories", [])[:3]
            ],
            "liquid_balance": getattr(summary, "current_liquid_balance", 0.0),
            "deposit_balance": getattr(summary, "total_deposit_balance", 0.0),
            "credit_debt": getattr(summary, "total_credit_debt", 0.0),
            "monthly_credit_payment": getattr(summary, "monthly_credit_payment", 0.0),
            "debt_burden_pct": getattr(summary, "debt_burden_ratio", 0.0),
            "runway_months": getattr(summary, "runway_months", 0.0),
            "is_family": getattr(summary, "is_family", False)
        }
        if dep_map:
            payload["deposits_by_currency"] = dep_map

        facts_block = ""
        if user_facts:
            masked_facts = [PIIGuardrailService.mask_text(f) for f in user_facts]
            facts_block = (
                "\nФАКТЫ О ПОЛЬЗОВАТЕЛЕ:\n"
                + "\n".join(f"- {f}" for f in masked_facts)
                + "\nУчитывай их в советах.\n"
            )

        prompt = (
            "Ты — финансовый консультант Smart Bujet. Дай строго 3 конкретных совета с цифрами (без пересчёта SQL):\n"
            f"СРЕЗ: {json.dumps(payload, ensure_ascii=False)}\n"
            f"{facts_block}"
            'ОТВЕТ СТРОГО JSON: {"where_to_cut": "1-2 предложения где сократить траты", "where_to_save": "1-2 предложения куда направить остаток", "what_to_watch": "1-2 предложения на что обратить внимание"}'
        )

        try:
            response = await client.aio.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=_build_gen_config(temperature=0.2, max_output_tokens=600),
            )
            data = json.loads(response.text.strip())
            result = {
                "where_to_cut": data.get("where_to_cut") or self._fallback_cut(summary),
                "where_to_save": data.get("where_to_save") or self._fallback_save(summary),
                "what_to_watch": data.get("what_to_watch") or self._fallback_watch(summary),
            }
            if cache_key is not None:
                if len(_ADVICE_CACHE) >= _MAX_ADVICE_CACHE_ENTRIES:
                    _ADVICE_CACHE.clear()
                _ADVICE_CACHE[cache_key] = (time.monotonic() + _ADVICE_CACHE_TTL_SECONDS, dict(result))
            return result
        except Exception as exc:
            logger.warning("AI generate_financial_advice fallback triggered: %s", exc)
            return self._generate_rule_based_advice(summary)

    def _generate_rule_based_advice(self, summary: Any) -> dict[str, str]:
        """Deterministic offline rule-based scoring engine."""
        return {
            "where_to_cut": self._fallback_cut(summary),
            "where_to_save": self._fallback_save(summary),
            "what_to_watch": self._fallback_watch(summary),
        }

    @staticmethod
    def _fallback_cut(s: Any) -> str:
        top_cat = getattr(s, "top_category_name", None)
        share = getattr(s, "top_category_share", 0.0)
        amt = getattr(s, "top_category_amount", 0.0)
        curr = getattr(s, "currency", "KZT")
        if top_cat and share > 25.0:
            reduction = round(amt * 0.15, 0)
            return (
                f"Наибольшая доля расходов приходится на «{top_cat}» ({share}%). "
                f"Сократив эти траты на 15%, вы сохраните около {reduction:,.0f} {curr}."
            )
        return "Оптимизируйте мелкие повседневные спонтанные траты и подписки для роста свободных средств."

    @staticmethod
    def _fallback_save(s: Any) -> str:
        debt = getattr(s, "total_credit_debt", 0.0)
        savings = getattr(s, "net_savings", 0.0)
        curr = getattr(s, "currency", "KZT")
        if debt > 0 and savings > 0:
            return (
                f"При свободном остатке {savings:,.0f} {curr} направьте часть на досрочное погашение "
                f"кредита (остаток {debt:,.0f} {curr}), чтобы сэкономить на процентах."
            )
        elif savings > 0:
            return (
                f"Свободный профицит {savings:,.0f} {curr} рекомендуется перевести на вклад или накопительный "
                f"счет для капитализации процентов."
            )
        return "Сформируйте резерв: откладывайте минимум 10% от любого входящего дохода до совершения трат."

    @staticmethod
    def _fallback_watch(s: Any) -> str:
        runway = getattr(s, "runway_months", 0.0)
        debt_burden = getattr(s, "debt_burden_ratio", 0.0)
        rate = getattr(s, "saving_rate", 0.0)
        savings = getattr(s, "net_savings", 0.0)
        curr = getattr(s, "currency", "KZT")
        if runway < 1.0:
            return (
                f"Внимание: финансовая подушка менее 1 месяца ({runway:.1f} мес.). "
                f"Приоритет номер один — сформировать неприкосновенный резерв на 3 месяца расходов."
            )
        elif debt_burden > 35.0:
            return (
                f"Кредитная нагрузка высока ({debt_burden}% от дохода). "
                f"Не берите новые обязательства до снижения долгового бремени."
            )
        elif rate < 0:
            return (
                f"Расходы превысили доходы за период на {abs(savings):,.0f} {curr}. "
                f"Необходимо пересмотреть траты для возврата в профицит."
            )
        return f"Отличный темп: норма сбережений {rate}%. Подушка безопасности закрывает {runway:.1f} мес."

    @staticmethod
    def _classify_fact_rule_based(text: str) -> dict[str, str]:
        lower = text.lower()
        if any(w in lower for w in ("цель", "накопить", "накоплю", "купить", "собрать", "планирую", "отпуск", "резерв", "подушк")):
            cat = "goal"
        elif any(w in lower for w in ("каждый", "каждое", "каждую", "всегда", "обычно", "привычка", "утро", "вечер", "кофе", "часто", "регулярно")):
            cat = "habit"
        elif any(w in lower for w in ("числа", "число", "зарплата", "аванс", "аренда", "график", "расписание", "понедельник", "пятниц", "ежемесячно")):
            cat = "schedule"
        elif any(w in lower for w in ("нельзя", "лимит", "запрет", "не тратить", "ограничение", "не больше", "максимум", "бюджет на")):
            cat = "constraint"
        else:
            cat = "other"
        return {"category": cat}

    async def classify_user_fact(self, text: str, user_id: int | None = None) -> dict[str, str]:
        """
        Classifies user memory fact into one of: 'goal', 'habit', 'schedule', 'constraint', 'other'.
        Instant (<1ms) when deterministic rules match; calls Gemini (thinking_budget=0) only for ambiguous facts.
        """
        rule_res = self._classify_fact_rule_based(text)
        cat = rule_res["category"]
        if cat != "other":
            return {"category": cat}

        if user_id is not None:
            allowed, _ = ai_rate_limiter.check_and_record(user_id)
            if not allowed:
                return {"category": cat}

        client = self.client
        if not client:
            return {"category": cat}

        masked_text = PIIGuardrailService.mask_text(text)
        prompt = (
            "Классифицируй факт пользователя: 'goal' (цель), 'habit' (привычка), "
            "'schedule' (даты/зарплата/платежи), 'constraint' (лимит/правило), 'other' (заметка).\n"
            f"Факт: \"{masked_text}\"\n"
            'СТРОГО JSON: {"category": "goal|habit|schedule|constraint|other"}'
        )
        try:
            res = await client.aio.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=_build_gen_config(temperature=0.1, max_output_tokens=64),
            )
            data = json.loads(res.text.strip())
            parsed_cat = data.get("category")
            if parsed_cat in {"goal", "habit", "schedule", "constraint", "other"}:
                return {"category": parsed_cat}
        except Exception as exc:
            logger.warning("Fact classification failed: %s", exc)

        return {"category": cat}


class AIRateLimiter:
    """Sliding-window per-user in-memory rate limiter."""
    def __init__(self, max_per_minute: int = 20, max_per_day: int = 200):
        self.max_per_minute = max_per_minute
        self.max_per_day = max_per_day
        self.user_requests = defaultdict(list)

    def check_and_record(self, user_id: int) -> tuple[bool, str]:
        now = time.time()
        minute_ago = now - 60
        day_ago = now - 86400

        timestamps = [t for t in self.user_requests[user_id] if t > day_ago]
        self.user_requests[user_id] = timestamps

        recent_minute = [t for t in timestamps if t > minute_ago]
        if len(recent_minute) >= self.max_per_minute:
            return False, "Превышен минутный лимит запросов к AI. Подождите 30 секунд."
        if len(timestamps) >= self.max_per_day:
            return False, "Превышен суточный лимит запросов к AI."

        self.user_requests[user_id].append(now)
        return True, ""


ai_rate_limiter = AIRateLimiter()
