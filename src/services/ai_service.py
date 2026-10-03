import json
import logging
import re
from decimal import Decimal
from typing import Any
from google import genai
from google.genai import types
from src.core.config import settings

logger = logging.getLogger(__name__)


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
        return {"items": []}

    if isinstance(data, list):
        items = [x for x in data if isinstance(x, dict)]
        return {"items": items}
    elif isinstance(data, dict):
        items = []
        for key in ("items", "transactions", "data", "results"):
            if isinstance(data.get(key), list):
                items = [x for x in data[key] if isinstance(x, dict)]
                break
        if not items and "item_name" in data:
            items = [data]
        return {
            "items": items,
            "discount_percent": data.get("discount_percent"),
            "discount_amount": data.get("discount_amount"),
            "total_paid": data.get("total_paid"),
        }
    return {"items": []}


class AIService:
    def __init__(self, api_key: str | None = None, model_name: str | None = None):
        self.api_key = api_key or settings.google_token
        self.client = genai.Client(api_key=self.api_key) if self.api_key else None
        self.model_name = model_name or settings.gemini_model

    @staticmethod
    def _format_assets_context(assets_context: Optional[list[dict[str, Any]]]) -> str:
        if not assets_context:
            return ""
        lines = [
            f"- ID: {a.get('id')}, Название: \"{a.get('name')}\", Тип: {a.get('type')}, Валюта: {a.get('currency')}"
            for a in assets_context
        ]
        return (
            "\nСуществующие счета и депозиты пользователя/семьи:\n"
            + "\n".join(lines)
            + "\nВАЖНО: Если операция связана с депозитом, вкладом или валютой, сопоставь её с одним из существующих счетов/депозитов пользователя выше (учитывай перестановку слов, синонимы, неточности распознавания, например «депозит Тоша и Айкоша» -> «Страховка Айкоша и Тоша»). В JSON обязательно заполни 'asset_account_id' (ID счета) и точный 'target_asset_name'.\n"
        )

    async def classify_text(
        self,
        text: str,
        categories: list[str],
        assets_context: Optional[list[dict[str, Any]]] = None
    ) -> dict[str, Any]:
        """Classify message into items and optional discount parameters."""
        if not self.client:
            return {
                "items": [{
                    "category": categories[0] if categories else "Обязательные расходы",
                    "type": "expense",
                    "amount": None,
                    "item_name": text
                }]
            }

        assets_block = self._format_assets_context(assets_context)
        prompt = (
            f"Ты финансовый ассистент приложения учёта бюджета Smart Bujet.\n"
            f"Определи ВСЕ позиции транзакций (расходы и доходы) и наличие скидки из сообщения: \"{text}\".\n"
            f"Доступные категории: {', '.join(categories)}.\n"
            f"{assets_block}\n"
            f"КРИТИЧЕСКИ ВАЖНО различать 4 типа операций:\n"
            f"- ДОХОДЫ (type: 'income'): «пришла зарплата», «зарплата», «получил», «заработал», «мне перевели», «пришел перевод», «аванс», «премия», «подарили», «кэшбэк», «подарок», «проценты по вкладу». Категории: «Зарплата», «Подарок», «Денежный перевод», «Проценты по вкладу».\n"
            f"- РАСХОДЫ (type: 'expense'): покупки товаров/услуг, еда, такси, исходящие переводы людям («я перевел жене», «перевел», «скинул», «купил хлеб», «потратил», «оплатил»). Переводы людям относи к категории «Денежный перевод».\n"
            f"- ПЕРЕВОД В АКТИВЫ / ДЕПОЗИТ / ВАЛЮТА (type: 'transfer_out'): деньги НЕ тратятся, а сохраняются в активах:\n"
            f"  * Пополнение вклада/депозита: «положил на депозит 100000», «закинул на вклад 50000», «в копилку 20000», «пополнила депозит Тоша и Айкоша» -> category: 'Депозит и вклады', type: 'transfer_out'.\n"
            f"  * Покупка иностранной валюты: «купил 100 долларов», «купил 200$ по 500», «купил евро на 50000» -> category: 'Покупка валюты', type: 'transfer_out', target_currency: 'USD'/'EUR', asset_amount: число_валюты.\n"
            f"- СНЯТИЕ ИЗ АКТИВОВ / ПРОДАЖА ВАЛЮТЫ (type: 'transfer_in'): «снял с депозита 50000», «вывел из копилки 10000», «продал 100 долларов» -> category: 'Снятие с депозита' или 'Продажа валюты', type: 'transfer_in'.\n\n"
            f"Каждую позицию выдели отдельно. Название позиции (item_name) пиши с заглавной буквы.\n"
            f"Если упомянута скидка (например 'скидка 5%', 'скидка 200', 'минус 10%'), обязательно заполни discount_percent или discount_amount.\n"
            f"Если указана итоговая сумма к оплате, заполни total_paid.\n"
            f"Верни ответ строго в виде JSON-объекта:\n"
            f'{{\n'
            f'  "items": [\n'
            f'    {{"category": "название из категорий", "type": "expense" или "income" или "transfer_out" или "transfer_in", "amount": число_в_базовой_валюте, "target_currency": "USD/EUR/KZT", "asset_amount": число_валюты_если_есть, "item_name": "Название позиции", "asset_account_id": "UUID_или_null", "target_asset_name": "название_актива_или_null"}}\n'
            f'  ],\n'
            f'  "discount_percent": число_или_null,\n'
            f'  "discount_amount": число_или_null,\n'
            f'  "total_paid": число_или_null\n'
            f'}}\n'
        )

        try:
            response = await self.client.aio.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1
                )
            )
            return normalize_receipt_payload(response.text)
        except Exception as exc:
            logger.error("AI classify_text failed: %s", exc)
            return {"items": []}

    async def parse_voice(
        self,
        audio_bytes: bytes,
        mime_type: str,
        categories: list[str],
        assets_context: Optional[list[dict[str, Any]]] = None
    ) -> dict[str, Any]:
        """In-memory voice message processing with discount and income extraction."""
        if not self.client:
            return {"items": []}

        audio_part = types.Part.from_bytes(data=audio_bytes, mime_type=mime_type)
        assets_block = self._format_assets_context(assets_context)
        prompt = (
            f"Прослушай аудиосообщение и выдели ВСЕ упомянутые расходы и доходы, а также скидки.\n"
            f"Доступные категории: {', '.join(categories)}.\n"
            f"{assets_block}\n"
            f"КРИТИЧЕСКИ ВАЖНО различать 4 типа операций:\n"
            f"- ДОХОДЫ (type: 'income'): «пришла зарплата», «зарплата», «получил», «заработал», «мне перевели», «пришел перевод», «аванс», «премия», «подарили», «кэшбэк», «подарок», «проценты по вкладу». Категории: «Зарплата», «Подарок», «Денежный перевод», «Проценты по вкладу».\n"
            f"- РАСХОДЫ (type: 'expense'): покупки, траты, исходящие переводы людям («я перевел жене», «перевел», «скинул», «купил», «потратил», «оплатил»). Исходящие переводы относи к категории «Денежный перевод».\n"
            f"- ПЕРЕВОД В АКТИВЫ / ДЕПОЗИТ / ВАЛЮТА (type: 'transfer_out'): деньги НЕ тратятся, а сохраняются в активах:\n"
            f"  * Пополнение вклада/депозита: «положил на депозит 100000», «закинул на вклад 50000», «в копилку 20000», «пополнила депозит Тоша и Айкоша» -> category: 'Депозит и вклады', type: 'transfer_out'.\n"
            f"  * Покупка иностранной валюты: «купил 100 долларов», «купил 200$ по 500», «купил евро на 50000» -> category: 'Покупка валюты', type: 'transfer_out', target_currency: 'USD'/'EUR', asset_amount: число_валюты.\n"
            f"- СНЯТИЕ ИЗ АКТИВОВ / ПРОДАЖА ВАЛЮТЫ (type: 'transfer_in'): «снял с депозита 50000», «вывел из копилки 10000», «продал 100 долларов» -> category: 'Снятие с депозита' или 'Продажа валюты', type: 'transfer_in'.\n\n"
            f"Каждую позицию выдели отдельно. Название каждой позиции (item_name) пиши с заглавной буквы.\n"
            f"Если названа скидка (например 'скидка 5%', 'скидка 249 тенге', 'минус 10%'), обязательно укажи discount_percent или discount_amount.\n"
            f"Если назван общий итог к оплате ('всего вышло 4733'), укажи total_paid.\n"
            f"Верни ответ строго в виде JSON-объекта:\n"
            f'{{\n'
            f'  "items": [\n'
            f'    {{"category": "название из категорий", "type": "expense" или "income" или "transfer_out" или "transfer_in", "amount": число_в_базовой_валюте, "target_currency": "USD/EUR/KZT", "asset_amount": число_валюты_если_есть, "item_name": "Название позиции", "asset_account_id": "UUID_или_null", "target_asset_name": "название_актива_или_null", "raw_text": "распознанный текст"}}\n'
            f'  ],\n'
            f'  "discount_percent": число_или_null,\n'
            f'  "discount_amount": число_или_null,\n'
            f'  "total_paid": число_или_null\n'
            f'}}\n'
        )

        try:
            response = await self.client.aio.models.generate_content(
                model=self.model_name,
                contents=[audio_part, prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1
                )
            )
            return normalize_receipt_payload(response.text)
        except Exception as exc:
            logger.error("AI parse_voice failed: %s", exc)
            return {"items": []}

    async def parse_receipt_photo(
        self,
        image_bytes: bytes,
        mime_type: str,
        categories: list[str]
    ) -> dict[str, Any]:
        """In-memory receipt photo processing with discount and total extraction."""
        if not self.client:
            return {"items": []}

        image_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
        prompt = (
            f"Проанализируй фотографию чека/квитанции.\n"
            f"Доступные категории: {', '.join(categories)}.\n"
            f"1. Извлеки все отдельные товарные позиции чека с их исходными ценами/суммами (item_name с заглавной буквы).\n"
            f"2. Если на чеке указана общая скидка чека (в процентах или фиксированной суммой, строка 'СКИДКА', 'ДИСКОНТ', 'БОНУСЫ'), обязательно укажи discount_percent и/или discount_amount.\n"
            f"3. В total_paid укажи итоговую фактически оплаченную сумму (строка 'ИТОГ', 'К ОПЛАТЕ', 'TOTAL').\n"
            f"Верни ответ строго в виде JSON-объекта:\n"
            f'{{\n'
            f'  "items": [\n'
            f'    {{"category": "название из категорий", "type": "expense", "amount": число, "item_name": "Название товара/услуги"}}\n'
            f'  ],\n'
            f'  "discount_percent": число_или_null,\n'
            f'  "discount_amount": число_или_null,\n'
            f'  "total_paid": число_или_null\n'
            f'}}\n'
        )

        try:
            response = await self.client.aio.models.generate_content(
                model=self.model_name,
                contents=[image_part, prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1
                )
            )
            return normalize_receipt_payload(response.text)
        except Exception as exc:
            logger.error("AI parse_receipt_photo failed: %s", exc)
            return {"items": []}

